"""Ingest MyFitnessPal diary days into the local database."""
from datetime import date, datetime, timezone

from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.myfitnesspal.client import hent_mfp_dag
from kaloriekassen.myfitnesspal.transform import meals_to_nutrition_entries
from kaloriekassen.sync_tracking import (
    date_range,
    finish_sync_run,
    record_coverage,
    requested_date_range,
    start_sync_run,
)


def _store_day(day: dict, run_id: str) -> None:
    """Store one diary day and its coverage atomically."""
    meals = day.get("meals", {})
    entries = meals_to_nutrition_entries(day["date"], meals)
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
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
                (entry["entry_id"], entry["date"], entry["meal_type"],
                 entry["source_meal_name"], entry["position"], entry["food_name"],
                 entry["consumed_at"], int(entry["time_is_estimated"]),
                 entry["calories"], entry["protein_g"], entry["carbs_g"],
                 entry["fat_g"], entry["sodium_mg"], entry["sugar_g"]))
        record_coverage(
            conn,
            "myfitnesspal",
            day["date"],
            "complete_data" if entries else "complete_empty",
            len(entries),
            run_id,
        )


def ingest_range(requested_from: date, requested_to: date) -> int:
    """Ingest an inclusive date range, committing each diary day separately."""
    if requested_from > requested_to:
        raise ValueError("requested_from must be on or before requested_to")

    run_id = start_sync_run("myfitnesspal", "myfitnesspal", requested_from, requested_to)
    fetched_count = 0
    stored_count = 0
    try:
        for requested_day in date_range(requested_from, requested_to):
            day = hent_mfp_dag(requested_day.isoformat())
            fetched_count += 1
            _store_day(day, run_id)
            stored_count += 1
        finish_sync_run(run_id, "success", fetched_count, stored_count)
        return stored_count
    except BaseException as error:
        with get_db_connection() as conn:
            for day in date_range(requested_day, requested_to):
                record_coverage(conn, "myfitnesspal", day, "failed", 0, run_id)
        finish_sync_run(
            run_id,
            "partial" if stored_count else "failed",
            fetched_count,
            stored_count,
            error,
        )
        raise


def ingest(days_back: int) -> int:
    """Ingest the latest number of days, including today."""
    requested_from, requested_to = requested_date_range(days_back)
    return ingest_range(requested_from, requested_to)
