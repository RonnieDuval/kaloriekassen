"""Ingest MyFitnessPal diary days into the local database."""
from datetime import datetime, timezone
from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.myfitnesspal.client import hent_mfp_seneste_dage
from kaloriekassen.myfitnesspal.transform import meals_to_nutrition_entries
from kaloriekassen.sync_tracking import (
    date_range,
    finish_sync_run,
    record_coverage,
    requested_date_range,
    start_sync_run,
)


def ingest(days_back: int) -> int:
    requested_from, requested_to = requested_date_range(days_back)
    run_id = start_sync_run("myfitnesspal", "myfitnesspal", requested_from, requested_to)
    try:
        days = hent_mfp_seneste_dage(days_back)
        days_by_date = {day["date"]: day for day in days}
        missing_days = 0
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

            for requested_day in date_range(requested_from, requested_to):
                day = days_by_date.get(requested_day.isoformat())
                if day is None:
                    missing_days += 1
                    record_coverage(
                        conn, "myfitnesspal", requested_day, "failed", 0, run_id
                    )
                    continue
                entry_count = len(
                    meals_to_nutrition_entries(day["date"], day.get("meals", {}))
                )
                record_coverage(
                    conn, "myfitnesspal", requested_day,
                    "complete_data" if entry_count else "complete_empty",
                    entry_count, run_id,
                )
        status = "partial" if missing_days else "success"
        finish_sync_run(run_id, status, len(days), len(days))
        return len(days)
    except BaseException as error:
        with get_db_connection() as conn:
            for day in date_range(requested_from, requested_to):
                record_coverage(conn, "myfitnesspal", day, "failed", 0, run_id)
        finish_sync_run(run_id, "failed", error=error)
        raise
