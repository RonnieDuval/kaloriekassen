"""Persist canonical measurements from a Withings getmeas response."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.sync_tracking import (
    date_range,
    finish_sync_run,
    record_coverage,
    requested_date_range,
    start_sync_run,
)
from kaloriekassen.withings.client import fetch_measurements
from kaloriekassen.withings.transform import transform_measure_groups


def ingest_measure_payload(payload: dict[str, Any]) -> int:
    """Upsert all supported body measurements in one getmeas payload."""
    rows = transform_measure_groups(payload)
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as connection:
        for row in rows:
            execute(
                connection,
                """INSERT INTO body_measurements
                   (measurement_id, measured_at, weight_kg, body_fat_pct,
                    fat_mass_kg, fat_free_mass_kg, source, source_id, payload,
                    fetched_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(measurement_id) DO UPDATE SET
                   measured_at=excluded.measured_at,
                   weight_kg=excluded.weight_kg,
                   body_fat_pct=excluded.body_fat_pct,
                   fat_mass_kg=excluded.fat_mass_kg,
                   fat_free_mass_kg=excluded.fat_free_mass_kg,
                   source=excluded.source,
                   source_id=excluded.source_id,
                   payload=excluded.payload,
                   fetched_at=excluded.fetched_at,
                   updated_at=excluded.updated_at""",
                (
                    row["measurement_id"],
                    row["measured_at"],
                    row.get("weight_kg"),
                    row.get("body_fat_pct"),
                    row.get("fat_mass_kg"),
                    row.get("fat_free_mass_kg"),
                    row["source"],
                    row["source_id"],
                    json_value(row["payload"]),
                    now,
                    now,
                ),
            )
    return len(rows)


def ingest(days_back: int) -> int:
    """Fetch and store Withings measurements for the requested date range."""
    start, end = requested_date_range(days_back)
    run_id = start_sync_run("withings", "withings", start, end)
    try:
        payload = fetch_measurements(start, end)
        transformed = transform_measure_groups(payload)
        stored = ingest_measure_payload(payload)
        counts: dict[date, int] = {day: 0 for day in date_range(start, end)}
        for row in transformed:
            measured_day = datetime.fromisoformat(row["measured_at"]).date()
            if measured_day in counts:
                counts[measured_day] += 1
        with get_db_connection() as connection:
            for day, count in counts.items():
                record_coverage(
                    connection,
                    "withings",
                    day,
                    "complete_data" if count else "complete_empty",
                    count,
                    run_id,
                )
        finish_sync_run(run_id, "success", len(transformed), stored)
        return stored
    except Exception as error:
        finish_sync_run(run_id, "failed", error=error)
        raise
