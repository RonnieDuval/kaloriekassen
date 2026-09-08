"""Replicate recent Google Health exercise records locally; never writes to Google."""
import json
from datetime import date, datetime, timedelta, timezone
from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.google_health.auth import get_credentials
from kaloriekassen.google_health.reader import fetch_exercises
from kaloriekassen.sync_tracking import finish_sync_run, start_sync_run


def _activity_date(interval: dict) -> str | None:
    """Return the exercise's civil start date, including its UTC offset."""
    civil_date = interval.get("civilStartTime", {}).get("date", {})
    if all(civil_date.get(part) is not None for part in ("year", "month", "day")):
        return date(
            int(civil_date["year"]),
            int(civil_date["month"]),
            int(civil_date["day"]),
        ).isoformat()

    start_time = interval.get("startTime")
    if not start_time:
        return None
    started_at = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    raw_offset = interval.get("startUtcOffset")
    if raw_offset and str(raw_offset).endswith("s"):
        offset = timezone(timedelta(seconds=int(str(raw_offset)[:-1])))
        started_at = started_at.astimezone(offset)
    return started_at.date().isoformat()


def _exercise_values(record: dict) -> tuple:
    exercise = record.get("exercise", {})
    interval = exercise.get("interval", {})
    metrics = exercise.get("metricsSummary", {})
    source_package = record.get("dataSource", {}).get("application", {}).get(
        "packageName"
    )
    distance_millimeters = metrics.get("distanceMillimeters")
    return (
        _activity_date(interval),
        interval.get("startTime"),
        interval.get("endTime"),
        exercise.get("exerciseType"),
        metrics.get("caloriesKcal"),
        metrics.get("steps"),
        (
            float(distance_millimeters) / 1000
            if distance_millimeters is not None
            else None
        ),
        source_package,
    )


def _normalize_stored_exercises(connection) -> None:
    """Populate normalized fields for payloads stored before this model existed."""
    legacy_records = execute(
        connection,
        """SELECT google_health_id, payload
           FROM raw_google_health_exercises
           WHERE activity_date IS NULL""",
    ).fetchall()
    for record_id, payload in legacy_records:
        values = _exercise_values(json.loads(payload))
        execute(
            connection,
            """UPDATE raw_google_health_exercises
               SET activity_date = ?, start_time = ?, end_time = ?,
                   exercise_type = ?, calories_kcal = ?, steps = ?,
                   distance_meters = ?, source_package = ?
               WHERE google_health_id = ?""",
            (*values, record_id),
        )


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
            _normalize_stored_exercises(conn)
            for record in records:
                record_id = record.get("name")
                if not record_id:
                    continue
                values = _exercise_values(record)
                execute(conn, """INSERT INTO raw_google_health_exercises
                    (google_health_id, activity_date, start_time, end_time,
                     exercise_type, calories_kcal, steps, distance_meters,
                     source_package, payload, fetched_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(google_health_id) DO UPDATE SET start_time=excluded.start_time,
                    activity_date=excluded.activity_date, end_time=excluded.end_time,
                    exercise_type=excluded.exercise_type,
                    calories_kcal=excluded.calories_kcal, steps=excluded.steps,
                    distance_meters=excluded.distance_meters,
                    source_package=excluded.source_package, payload=excluded.payload,
                    fetched_at=excluded.fetched_at, updated_at=excluded.updated_at""",
                    (
                        record_id,
                        *values,
                        json_value(record),
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                    ))
                stored_count += 1
        status = "success" if stored_count == len(records) else "partial"
        finish_sync_run(run_id, status, len(records), stored_count)
        return len(records)
    except BaseException as error:
        finish_sync_run(run_id, "failed", error=error)
        raise
