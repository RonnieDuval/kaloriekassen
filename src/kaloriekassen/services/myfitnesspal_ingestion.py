"""Ingest MyFitnessPal diary days into the local database."""
from datetime import datetime, timezone
from kaloriekassen.database.connection import get_db_connection, json_value
from kaloriekassen.database.nutrition import aggregate_meals_to_totals
from kaloriekassen.integrations.myfitnesspal.client import hent_mfp_seneste_dage


def ingest(days_back: int, visible: bool = False) -> int:
    days = hent_mfp_seneste_dage(days_back, visible=visible)
    with get_db_connection() as conn:
        for day in days:
            totals = aggregate_meals_to_totals(day.get("meals", {}))
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""INSERT INTO raw_mfp
                (date, meals_detail, calories_in, protein, carbs, fat, sodium, sugar, fetched_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET meals_detail=excluded.meals_detail,
                calories_in=excluded.calories_in, protein=excluded.protein, carbs=excluded.carbs,
                fat=excluded.fat, sodium=excluded.sodium, sugar=excluded.sugar,
                fetched_at=excluded.fetched_at, updated_at=excluded.updated_at""",
                (day["date"], json_value(day.get("meals", {})), totals["calories_in"], totals["protein"],
                 totals["carbs"], totals["fat"], totals["sodium"], totals["sugar"], now, now))
    return len(days)
