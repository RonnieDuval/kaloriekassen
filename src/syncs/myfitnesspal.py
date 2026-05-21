"""MyFitnessPal data sync adapter using Playwright browser automation."""
import datetime as dt
import json
import logging
from typing import Dict, List

from src.db_helpers import aggregate_meals_to_totals
from src.sync_base import BaseSyncAdapter

logger = logging.getLogger(__name__)


class MyFitnessPalSync(BaseSyncAdapter):
    """Sync last 7 days of MyFitnessPal nutrition data using browser automation."""

    table_name = "raw_mfp"
    columns = [
        "date",
        "meals_detail",
        "calories_in",
        "protein",
        "carbs",
        "fat",
        "sodium",
        "sugar",
        "fetched_at",
    ]

    def fetch_data(self) -> List[Dict]:
        """Fetch last x days of MyFitnessPal meal data via Playwright automation.
        
        Returns:
            List of dicts with date, meals_detail (JSONB), and aggregated totals.
        """
        # Import here to avoid circular dependency and to keep browser logic isolated
        from MYFITNESSPAL.mfp_chatgpt import hent_mfp_seneste_dage

        logger.info("Fetching MyFitnessPal data for last %d days via browser automation...", self.days_back)

        try:
            mfp_data = hent_mfp_seneste_dage(self.days_back, visible=False)
        except Exception as e:
            logger.error("Failed to fetch MyFitnessPal data: %s", str(e))
            raise

        if not mfp_data:
            logger.warning("No MyFitnessPal data returned")
            mfp_data = []

        # Index fetched data by date for quick lookup
        fetched_by_date: Dict[dt.date, Dict] = {}
        for day_data in mfp_data:
            date_str = day_data.get("date")
            if date_str:
                try:
                    date_obj = dt.date.fromisoformat(date_str)
                    fetched_by_date[date_obj] = day_data
                except ValueError:
                    logger.warning("Invalid date format: %s", date_str)
                    continue

        # Build complete 7-day range (fill missing days)
        today = dt.date.today()
        rows: List[Dict] = []
        now = dt.datetime.now(dt.timezone.utc)

        for offset in range(self.days_back):
            day = today - dt.timedelta(days=offset)

            if day in fetched_by_date:
                day_data = fetched_by_date[day]
                meals_detail = day_data.get("meals", {})
            else:
                # No data for this day, use empty meals
                meals_detail = {
                    "Breakfast": [],
                    "Lunch": [],
                    "Dinner": [],
                    "Snacks": [],
                }

            # Aggregate totals from meals
            totals = aggregate_meals_to_totals(meals_detail)

            # Build row for database upsert
            row = {
                "date": day,
                "meals_detail": json.dumps(meals_detail),  # Convert to JSON string for psycopg2
                "calories_in": totals["calories_in"],
                "protein": totals["protein"],
                "carbs": totals["carbs"],
                "fat": totals["fat"],
                "sodium": totals["sodium"],
                "sugar": totals["sugar"],
                "fetched_at": now,
            }

            rows.append(row)

        logger.info("Prepared %d days of MyFitnessPal data for upsert", len(rows))
        return rows
