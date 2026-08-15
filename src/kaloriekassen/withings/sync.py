"""Persist canonical measurements from a Withings getmeas response."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kaloriekassen.db import execute, get_db_connection, json_value
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
