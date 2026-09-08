"""Backfill Intervals average heart rate onto existing Google exercises."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.google_health.auth import get_credentials
from kaloriekassen.google_health.client import patch_exercise_record
from kaloriekassen.google_health.mapper import map_single_activity_to_google_exercise
from kaloriekassen.sync_tracking import finish_sync_run, start_sync_run


logger = logging.getLogger(__name__)


def _utc_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_matches_activity(
    record: dict[str, Any],
    mapped: dict[str, Any],
) -> bool:
    source = record.get("dataSource", {})
    exercise = record.get("exercise", {})
    expected = mapped["exercise"]
    if source.get("platform") != "GOOGLE_WEB_API":
        return False
    if source.get("recordingMethod") != "ACTIVELY_MEASURED":
        return False
    if exercise.get("exerciseType") != expected.get("exerciseType"):
        return False
    actual_distance = exercise.get("metricsSummary", {}).get("distanceMillimeters")
    expected_distance = expected.get("metricsSummary", {}).get("distanceMillimeters")
    return actual_distance == expected_distance


def _load_exported_activities(oldest: date) -> list[tuple[str, str | None, dict[str, Any]]]:
    with get_db_connection() as connection:
        rows = execute(
            connection,
            """SELECT e.intervals_activity_id, e.google_health_id, i.payload
               FROM google_health_exports e
               JOIN raw_intervals i ON i.activity_id = e.intervals_activity_id
               WHERE e.status = 'sent' AND substr(i.started_at, 1, 10) >= ?
               ORDER BY i.started_at""",
            (oldest.isoformat(),),
        ).fetchall()
    return [(row[0], row[1], json.loads(row[2])) for row in rows]


def _load_google_exercises() -> dict[datetime, list[tuple[str, dict[str, Any]]]]:
    by_start: dict[datetime, list[tuple[str, dict[str, Any]]]] = {}
    with get_db_connection() as connection:
        rows = execute(
            connection,
            """SELECT google_health_id, start_time, payload
               FROM raw_google_health_exercises
               WHERE start_time IS NOT NULL""",
        ).fetchall()
    for google_health_id, start_time, payload in rows:
        by_start.setdefault(_utc_instant(start_time), []).append(
            (google_health_id, json.loads(payload))
        )
    return by_start


def backfill_average_heart_rate(days_back: int = 90) -> int:
    """Patch uniquely matched, already-exported exercises with average heart rate."""
    if days_back < 1:
        raise ValueError("days_back must be at least 1")
    oldest = date.today() - timedelta(days=days_back - 1)
    run_id = start_sync_run(
        "google-health-heart-rate-backfill",
        "google-health",
        oldest,
        date.today(),
    )
    updated = 0
    eligible = 0
    issues: list[str] = []
    try:
        exported = _load_exported_activities(oldest)
        google_by_start = _load_google_exercises()
        access_token: str | None = None

        for activity_id, stored_google_id, activity in exported:
            if activity.get("average_heartrate") is None:
                continue
            eligible += 1
            mapped = map_single_activity_to_google_exercise(activity)
            google_health_id = stored_google_id
            if not google_health_id:
                start = _utc_instant(activity["start_date"])
                matches = [
                    candidate_id
                    for candidate_id, record in google_by_start.get(start, [])
                    if _record_matches_activity(record, mapped)
                ]
                if len(matches) != 1:
                    issues.append(
                        f"{activity_id}: expected one Google match, found {len(matches)}"
                    )
                    continue
                google_health_id = matches[0]

            try:
                if access_token is None:
                    access_token = get_credentials().token
                patch_exercise_record(access_token, google_health_id, mapped)
            except Exception as error:
                issues.append(f"{activity_id}: {type(error).__name__}: {error}")
                continue

            with get_db_connection() as connection:
                execute(
                    connection,
                    """UPDATE google_health_exports
                       SET google_health_id = ?, request_payload = ?, last_error = NULL
                       WHERE intervals_activity_id = ?""",
                    (google_health_id, json_value(mapped), activity_id),
                )
            updated += 1

        if issues:
            error = RuntimeError("; ".join(issues[:5]))
            finish_sync_run(
                run_id,
                "partial" if updated else "failed",
                fetched_count=eligible,
                stored_count=updated,
                error=error,
            )
            raise error

        finish_sync_run(
            run_id,
            "success",
            fetched_count=eligible,
            stored_count=updated,
        )
        return updated
    except BaseException as error:
        if not issues:
            finish_sync_run(
                run_id,
                "partial" if updated else "failed",
                fetched_count=eligible,
                stored_count=updated,
                error=error,
            )
        raise
