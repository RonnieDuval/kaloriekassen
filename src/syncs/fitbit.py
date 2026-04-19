"""Fitbit data sync adapter."""
import datetime as dt
import logging
import os
from typing import Dict, List

import requests

from src.sync_base import BaseSyncAdapter

logger = logging.getLogger(__name__)


class FitbitSync(BaseSyncAdapter):
    """Sync last 7 days of Fitbit activity data (calories, steps, distance)."""

    table_name = "raw_fitbit"
    columns = ["date", "calories_out", "distance_km", "steps"]

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
            logger.debug(f"Fetching Fitbit {metric}...")
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
