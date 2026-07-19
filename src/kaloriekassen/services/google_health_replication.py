"""Replicate Google Health exercise records locally; never writes to Google."""
from datetime import datetime, timezone
from kaloriekassen.database.connection import execute, get_db_connection, json_value
from kaloriekassen.integrations.google_health.auth import get_credentials
from kaloriekassen.integrations.google_health.reader import fetch_exercises


def replicate() -> int:
    records = fetch_exercises(get_credentials().token)
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
    return len(records)
