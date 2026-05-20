"""Intervals.icu data fetcher."""
import datetime as dt
import logging
import os
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class IntervalsFetcher:
    """Fetch workout data from Intervals.icu API, with configurable date range."""

    def __init__(self, days_back: int = 7):
        """
        Initialize fetcher.
        
        Args:
            days_back: Number of days to fetch (default 7)
        """
        self.days_back = days_back
        self.api_key = os.getenv("INTERVALS_API_KEY", "").strip()
        self.athlete_id = os.getenv("INTERVALS_ATHLETE_ID", "").strip()

        if not self.api_key or not self.athlete_id:
            raise ValueError(
                "Missing INTERVALS_API_KEY or INTERVALS_ATHLETE_ID environment variables"
            )

    def fetch_raw(self) -> List[Dict]:
        """
        Fetch raw activities from Intervals.icu API.
        
        Returns:
            List of raw activity dicts from API
        """
        today = dt.date.today()
        oldest = today - dt.timedelta(days=self.days_back - 1)

        url = f"https://intervals.icu/api/v1/athlete/{self.athlete_id}/activities"
        params = {
            "oldest": oldest.isoformat(),
            "newest": today.isoformat(),
        }

        logger.info("Fetching Intervals.icu data for last %d days...", self.days_back)
        resp = requests.get(url, params=params, auth=("API_KEY", self.api_key), timeout=30)
        resp.raise_for_status()
        activities = resp.json()
        logger.info("Fetched %d activities from Intervals.icu", len(activities))

        return activities

    def fetch_aggregated(self) -> List[Dict]:
        """
        Fetch and aggregate activities by day.
        
        Returns:
            List of dicts with daily aggregated metrics:
            - date (dt.date)
            - calories_out (int)
            - distance_km (float)
            - elevation_gain (int)
            - workout_type (str or None)
            - elapsed_time (int)
        """
        activities = self.fetch_raw()

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
                    "elapsed_time": 0,
                },
            )
            metrics["calories_out"] += int(item.get("calories", 0) or 0)
            metrics["distance_km"] += float(item.get("distance", 0) or 0) / 1000
            metrics["elevation_gain"] += int(item.get("total_elevation_gain", 0) or 0)
            metrics["elapsed_time"] += int(item.get("elapsed_time", 0) or 0)
            workout_type = item.get("type")
            if workout_type:
                metrics["workout_type"] = workout_type

        # Build complete date range (fill missing days with zeros)
        today = dt.date.today()
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
                        "elapsed_time": 0,
                    },
                )
            )

        logger.info("Aggregated %d days from %d activities", len(rows), len(activities))
        return rows
