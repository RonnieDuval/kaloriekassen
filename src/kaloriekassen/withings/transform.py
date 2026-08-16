"""Transform Withings getmeas payloads to canonical body measurements."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


MEASURE_FIELDS = {
    1: "weight_kg",
    5: "fat_free_mass_kg",
    6: "body_fat_pct",
    8: "fat_mass_kg",
}


def transform_measure_groups(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one canonical row per Withings measurement group."""
    groups = payload.get("body", {}).get("measuregrps", [])
    rows: list[dict[str, Any]] = []
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, dict) or group.get("grpid") is None:
            continue
        values: dict[str, float] = {}
        for measure in group.get("measures", []):
            if not isinstance(measure, dict):
                continue
            field = MEASURE_FIELDS.get(measure.get("type"))
            if field is None or measure.get("value") is None:
                continue
            values[field] = float(measure["value"]) * (10 ** int(measure.get("unit", 0)))
        if not values:
            continue

        measured_at = datetime.fromtimestamp(
            int(group["date"]),
            tz=timezone.utc,
        ).isoformat()
        rows.append(
            {
                "measurement_id": f"withings:{group['grpid']}",
                "measured_at": measured_at,
                "source": "withings",
                "source_id": str(group["grpid"]),
                "payload": group,
                **values,
            }
        )
    return rows
