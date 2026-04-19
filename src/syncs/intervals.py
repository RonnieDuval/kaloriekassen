"""Intervals.icu data sync adapter."""
import datetime as dt
import logging
import os
from typing import Dict, List

import requests

from src.sync_base import BaseSyncAdapter

logger = logging.getLogger(__name__)


class IntervalsSync(BaseSyncAdapter):
    """Sync last 7 days of Intervals.icu workout data aggregated by day."""

    table_name = "raw_intervals"
    columns = ["date", "calories_out", "distance_km", "elevation_gain", "workout_type"]

    def fetch_data(self) -> List[Dict]:
        """Fetch last 7 days of Intervals.icu activity data, aggregated by day."""
        api_key = os.getenv("INTERVALS_API_KEY", "").strip()
        athlete_id = os.getenv("INTERVALS_ATHLETE_ID", "").strip()

        if not api_key or not athlete_id:
            raise ValueError(
                "Missing INTERVALS_API_KEY or INTERVALS_ATHLETE_ID environment variables"
            )

        today = dt.date.today()
        oldest = today - dt.timedelta(days=6)

        url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/activities"
        params = {
            "oldest": oldest.isoformat(),
            "newest": today.isoformat(),
        }

        logger.info("Fetching Intervals.icu data...")
        resp = requests.get(url, params=params, auth=("API_KEY", api_key), timeout=30)
        resp.raise_for_status()
        activities = resp.json()

        # Aggregate activities by day
        per_day: Dict[dt.date, Dict] = {}
        for item in activities:
            day = dt.date.fromisoformat(item.get("start_date_local", "")[:10])
            metrics = per_day.setdefault(
                day,
                {
                    "date": day,
                    "calories_out": 0,
                    "distance_km": 0.0,
                    "elevation_gain": 0,
                    "workout_type": None,
                },
            )

            metrics["calories_out"] += int(item.get("calories", 0) or 0)
            metrics["distance_km"] += float(item.get("distance", 0) or 0) / 1000
            metrics["elevation_gain"] += int(item.get("total_elevation_gain", 0) or 0)
            workout_type = item.get("type")
            if workout_type:
                metrics["workout_type"] = workout_type

        # Build complete 7-day range (fill missing days with zeros)
        rows: List[Dict] = []
        for offset in range(self.days_back):
            day = today - dt.timedelta(days=offset)
            rows.append(
                per_day.get(
                    day,
                    {
                        "date": day,
                        "calories_out": 0,
                        "distance_km": 0.0,
                        "elevation_gain": 0,
                        "workout_type": None,
                    },
                )
            )

        logger.info("Fetched %d days from Intervals.icu (aggregated from %d activities)", len(rows), len(activities))
        return rows
