"""MyFitnessPal data sync adapter."""
import datetime as dt
import logging
import os
from typing import Dict, List

import myfitnesspal

from src.pipeline.normalize_nutrition import normalize_nutrition_entries
from src.sync_base import BaseSyncAdapter

logger = logging.getLogger(__name__)


class MFPSync(BaseSyncAdapter):
    """Sync last 7 days of MyFitnessPal food diary (calories_in, protein, carbs, fat)."""

    table_name = "raw_mfp"
    columns = ["date", "calories_in", "protein", "carbs", "fat"]

    def __init__(self):
        super().__init__()
        self._raw_events: List[Dict] = []

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
        raw_events: List[Dict] = []

        for offset in range(self.days_back):
            day = today - dt.timedelta(days=offset)
            logger.debug("Fetching MFP data for %s...", day)

            diary = client.get_date(day.year, day.month, day.day)
            totals = diary.totals

            for meal in getattr(diary, "meals", []) or []:
                meal_name = getattr(meal, "name", "meal")
                for idx, entry in enumerate(getattr(meal, "entries", []) or []):
                    raw_events.append(
                        {
                            "source": "mfp",
                            "source_event_type": "meal_entry",
                            "source_event_id": f"{day.isoformat()}:{meal_name}:{idx}:{getattr(entry, 'name', '')}",
                            "event_ts": f"{day.isoformat()}T12:00:00",
                            "event_date": day,
                            "payload": {
                                "meal_name": meal_name,
                                "food_name": getattr(entry, "name", None),
                                "nutrition_information": getattr(entry, "nutrition_information", {}),
                            },
                        }
                    )

            rows.append(
                {
                    "date": day,
                    "calories_in": int(totals.get("calories", 0) or 0),
                    "protein": int(totals.get("protein", 0) or 0),
                    "carbs": int(totals.get("carbohydrates", 0) or 0),
                    "fat": int(totals.get("fat", 0) or 0),
                }
            )

        self._raw_events = raw_events

        logger.info("Fetched %d days from MyFitnessPal", len(rows))
        return rows

    def fetch_raw_events(self) -> List[Dict]:
        return self._raw_events

    def after_sync(self) -> None:
        normalize_nutrition_entries(days_back=self.days_back)
