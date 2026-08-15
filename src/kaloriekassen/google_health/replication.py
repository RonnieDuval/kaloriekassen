"""Replicate recent Google Health exercise records locally; never writes to Google."""
from datetime import date, datetime, timedelta, timezone
from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.google_health.auth import get_credentials
from kaloriekassen.google_health.reader import fetch_exercises
from kaloriekassen.sync_tracking import finish_sync_run, start_sync_run


def replicate(days_back: int = 7) -> int:
    if days_back < 1:
        raise ValueError("days_back must be at least 1")

    start_date = date.today() - timedelta(days=days_back - 1)
    end_date = date.today() + timedelta(days=1)
    filter_expression = (
        f'exercise.interval.civil_start_time >= "{start_date.isoformat()}T00:00:00" '
        f'AND exercise.interval.civil_start_time < "{end_date.isoformat()}T00:00:00"'
    )
    run_id = start_sync_run(
        "google-health-read",
        "google-health",
        start_date,
        date.today(),
    )
    try:
        records = fetch_exercises(
            get_credentials().token,
            filter_expression=filter_expression,
        )
        stored_count = 0
        with get_db_connection() as conn:
            for record in records:
                exercise = record.get("exercise", {})
                interval = exercise.get("interval", {})
                record_id = record.get("name")
                if not record_id:
                    continue
                execute(conn, """INSERT INTO raw_google_health_exercises
                    (google_health_id, start_time, end_time, exercise_type, payload, fetched_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(google_health_id) DO UPDATE SET start_time=excluded.start_time,
                    end_time=excluded.end_time, exercise_type=excluded.exercise_type, payload=excluded.payload,
                    fetched_at=excluded.fetched_at, updated_at=excluded.updated_at""",
                    (record_id, interval.get("startTime"), interval.get("endTime"), exercise.get("exerciseType"),
                     json_value(record), datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
                stored_count += 1
        status = "success" if stored_count == len(records) else "partial"
        finish_sync_run(run_id, status, len(records), stored_count)
        return len(records)
    except BaseException as error:
        finish_sync_run(run_id, "failed", error=error)
        raise
