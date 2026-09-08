"""Ingest individual Intervals activities into the local database."""
from collections import Counter
from datetime import datetime, timezone
from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.intervals.client import IntervalsFetcher
from kaloriekassen.sync_tracking import (
    date_range,
    finish_sync_run,
    record_coverage,
    requested_date_range,
    start_sync_run,
)


def ingest(days_back: int) -> int:
    requested_from, requested_to = requested_date_range(days_back)
    run_id = start_sync_run("intervals", "intervals", requested_from, requested_to)
    try:
        activities = IntervalsFetcher(days_back).fetch_raw()
        activity_counts = Counter(
            str(activity.get("start_date_local") or activity.get("start_date"))[:10]
            for activity in activities
        )
        with get_db_connection() as conn:
            for activity in activities:
                activity_id = str(
                    activity.get("id")
                    or activity.get("activity_id")
                    or activity["start_date_local"]
                )
                now = datetime.now(timezone.utc).isoformat()
                execute(conn, """INSERT INTO raw_intervals
                    (activity_id, started_at, activity_type, calories_out, distance_meters,
                     elevation_gain_meters, elapsed_time_seconds, payload, fetched_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(activity_id) DO UPDATE SET
                    started_at=excluded.started_at, activity_type=excluded.activity_type,
                    calories_out=excluded.calories_out, distance_meters=excluded.distance_meters,
                    elevation_gain_meters=excluded.elevation_gain_meters,
                    elapsed_time_seconds=excluded.elapsed_time_seconds, payload=excluded.payload,
                    fetched_at=excluded.fetched_at, updated_at=excluded.updated_at""",
                    (activity_id, activity["start_date_local"], activity.get("type"), activity.get("calories"),
                     activity.get("distance"), activity.get("total_elevation_gain"), activity.get("elapsed_time"),
                     json_value(activity), now, now))
            for day in date_range(requested_from, requested_to):
                count = activity_counts[day.isoformat()]
                record_coverage(
                    conn, "intervals", day,
                    "complete_data" if count else "complete_empty",
                    count, run_id,
                )
        finish_sync_run(run_id, "success", len(activities), len(activities))
        return len(activities)
    except BaseException as error:
        with get_db_connection() as conn:
            for day in date_range(requested_from, requested_to):
                record_coverage(conn, "intervals", day, "failed", 0, run_id)
        finish_sync_run(run_id, "failed", error=error)
        raise
