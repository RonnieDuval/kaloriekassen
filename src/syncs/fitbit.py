"""Fitbit data sync adapter."""
import datetime as dt
import logging
import os
from typing import Dict, List

import requests

from src.pipeline import normalize_activities
from src.sync_base import BaseSyncAdapter

logger = logging.getLogger(__name__)


class FitbitSync(BaseSyncAdapter):
    """Sync last 7 days of Fitbit activity data (calories, steps, distance)."""

    table_name = "raw_fitbit"
    columns = ["date", "calories_out", "distance_km", "steps"]

    def __init__(self):
        super().__init__()
        self._raw_events: List[Dict] = []

    def fetch_data(self) -> List[Dict]:
        """Fetch last 7 days of Fitbit data."""
        access_token = os.getenv("FITBIT_ACCESS_TOKEN", "").strip()
        user_id = os.getenv("FITBIT_USER_ID", "-").strip()

        if not access_token:
            raise ValueError("Missing FITBIT_ACCESS_TOKEN environment variable")

        headers = {"Authorization": f"Bearer {access_token}"}
        today = dt.date.today()
        oldest = today - dt.timedelta(days=6)

        base = f"https://api.fitbit.com/1/user/{user_id}"
        endpoints = {
            "calories": f"{base}/activities/calories/date/{oldest.isoformat()}/{today.isoformat()}.json",
            "steps": f"{base}/activities/steps/date/{oldest.isoformat()}/{today.isoformat()}.json",
            "distance": f"{base}/activities/distance/date/{oldest.isoformat()}/{today.isoformat()}.json",
        }

        series = {}
        for metric, url in endpoints.items():
            logger.debug("Fetching Fitbit %s...", metric)
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()

            metric_key = f"activities-{metric}"
            series[metric] = {
                dt.date.fromisoformat(item["dateTime"]): (
                    int(float(item.get("value") or 0))
                    if metric != "distance"
                    else float(item.get("value") or 0)
                )
                for item in resp.json().get(metric_key, [])
            }

        raw_events: List[Dict] = []
        for offset in range(self.days_back):
            day = today - dt.timedelta(days=offset)
            activities_url = f"{base}/activities/date/{day.isoformat()}.json"
            resp = requests.get(activities_url, headers=headers, timeout=30)
            resp.raise_for_status()
            day_payload = resp.json()

            for activity in day_payload.get("activities", []):
                raw_events.append(
                    {
                        "source": "fitbit",
                        "source_event_type": "activity",
                        "source_event_id": str(activity.get("logId") or ""),
                        "event_ts": f"{day.isoformat()}T{activity.get('startTime', '00:00')}",
                        "event_date": day,
                        "payload": activity,
                    }
                )

        self._raw_events = raw_events

        rows: List[Dict] = []
        for offset in range(self.days_back):
            day = today - dt.timedelta(days=offset)
            rows.append(
                {
                    "date": day,
                    "calories_out": series["calories"].get(day, 0),
                    "steps": series["steps"].get(day, 0),
                    "distance_km": series["distance"].get(day, 0.0),
                }
            )

        logger.info("Fetched %d days from Fitbit", len(rows))
        return rows

    def fetch_raw_events(self) -> List[Dict]:
        return self._raw_events

    def after_sync(self) -> None:
        normalize_activities(days_back=self.days_back)
