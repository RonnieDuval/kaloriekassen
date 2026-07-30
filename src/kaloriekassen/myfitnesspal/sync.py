"""Ingest MyFitnessPal diary days into the local database."""
from datetime import datetime, timezone
from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.myfitnesspal.client import hent_mfp_seneste_dage
from kaloriekassen.myfitnesspal.transform import meals_to_nutrition_entries


def ingest(days_back: int) -> int:
    days = hent_mfp_seneste_dage(days_back)
    with get_db_connection() as conn:
        for day in days:
            meals = day.get("meals", {})
            entries = meals_to_nutrition_entries(day["date"], meals)
            now = datetime.now(timezone.utc).isoformat()
            execute(conn, """INSERT INTO raw_mfp
                (date, meals_detail, fetched_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET meals_detail=excluded.meals_detail,
                fetched_at=excluded.fetched_at, updated_at=excluded.updated_at""",
                (day["date"], json_value(meals), now, now))
            execute(conn, "DELETE FROM nutrition_entries WHERE date = ?", (day["date"],))
            for entry in entries:
                execute(conn, """INSERT INTO nutrition_entries
                    (entry_id, date, meal_type, source_meal_name, position, food_name,
                     consumed_at, time_is_estimated, calories, protein_g, carbs_g,
                     fat_g, sodium_mg, sugar_g)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (entry["entry_id"], entry["date"], entry["meal_type"], entry["source_meal_name"],
                     entry["position"], entry["food_name"], entry["consumed_at"],
                     int(entry["time_is_estimated"]), entry["calories"], entry["protein_g"],
                     entry["carbs_g"], entry["fat_g"], entry["sodium_mg"], entry["sugar_g"]))
    return len(days)
