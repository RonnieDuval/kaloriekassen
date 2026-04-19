"""MyFitnessPal data sync adapter."""
import datetime as dt
import logging
import os
from typing import Dict, List

import myfitnesspal

from src.sync_base import BaseSyncAdapter

logger = logging.getLogger(__name__)


class MFPSync(BaseSyncAdapter):
    """Sync last 7 days of MyFitnessPal food diary (calories_in, protein, carbs, fat)."""

    table_name = "raw_mfp"
    columns = ["date", "calories_in", "protein", "carbs", "fat"]

    def fetch_data(self) -> List[Dict]:
        """Fetch last 7 days of MyFitnessPal food diary data."""
        username = os.getenv("MFP_USERNAME", "").strip()
        password = os.getenv("MFP_PASSWORD", "").strip()

        if not username or not password:
            raise ValueError("Missing MFP_USERNAME or MFP_PASSWORD environment variables")

        logger.info("Connecting to MyFitnessPal...")
        client = myfitnesspal.Client(username, password)

        today = dt.date.today()
        rows: List[Dict] = []

        for offset in range(self.days_back):
            day = today - dt.timedelta(days=offset)
            logger.debug(f"Fetching MFP data for {day}...")

            diary = client.get_date(day.year, day.month, day.day)
            totals = diary.totals

            rows.append(
                {
                    "date": day,
                    "calories_in": int(totals.get("calories", 0) or 0),
                    "protein": int(totals.get("protein", 0) or 0),
                    "carbs": int(totals.get("carbohydrates", 0) or 0),
                    "fat": int(totals.get("fat", 0) or 0),
                }
            )

        logger.info("Fetched %d days from MyFitnessPal", len(rows))
        return rows
