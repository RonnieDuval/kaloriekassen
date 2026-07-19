"""Ingest individual Intervals activities into the local database."""
from datetime import datetime, timezone
from kaloriekassen.database.connection import execute, get_db_connection, json_value
from kaloriekassen.integrations.intervals.client import IntervalsFetcher


def ingest(days_back: int) -> int:
    activities = IntervalsFetcher(days_back).fetch_raw()
    with get_db_connection() as conn:
        for activity in activities:
            activity_id = str(activity.get("id") or activity.get("activity_id") or activity["start_date_local"])
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
                 json_value(activity), datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
    return len(activities)
