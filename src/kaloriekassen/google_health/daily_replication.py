"""Replicate activity and energy rollups from Google Health."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.google_health.auth import get_credentials
from kaloriekassen.google_health.reader import fetch_daily_rollups
from kaloriekassen.sync_tracking import (
    date_range,
    finish_sync_run,
    record_coverage,
    start_sync_run,
)


MAX_ENERGY_ROLLUP_DAYS = 14
ROLLUP_TYPES = (
    "steps",
    "active-energy-burned",
    "total-calories",
)


def _rollup_date(record: dict[str, Any]) -> date:
    value = record["civilStartTime"]["date"]
    return date(int(value["year"]), int(value["month"]), int(value["day"]))


def _number(record: dict[str, Any], object_name: str, field: str) -> float | None:
    value = record.get(object_name, {}).get(field)
    return float(value) if value is not None else None


def _fetch_rollups(
    access_token: str,
    start_date: date,
    end_date: date,
) -> tuple[dict[date, dict[str, Any]], int]:
    """Fetch a closed-open range, respecting Google's 14-day energy limit."""
    by_date: dict[date, dict[str, Any]] = {}
    fetched_count = 0
    chunk_start = start_date

    while chunk_start < end_date:
        chunk_end = min(chunk_start + timedelta(days=MAX_ENERGY_ROLLUP_DAYS), end_date)
        for data_type in ROLLUP_TYPES:
            records = fetch_daily_rollups(
                access_token,
                data_type,
                chunk_start,
                chunk_end,
            )
            fetched_count += len(records)
            for record in records:
                by_date.setdefault(_rollup_date(record), {})[data_type] = record
        chunk_start = chunk_end

    return by_date, fetched_count


def _replicate_range(
    job: str,
    source: str,
    start_date: date,
    requested_to: date,
) -> int:
    """Store Google rollups for an inclusive civil-date range."""
    run_id = start_sync_run(
        job,
        source,
        start_date,
        requested_to,
    )
    fetched_count = 0
    stored_count = 0

    try:
        records_by_date, fetched_count = _fetch_rollups(
            get_credentials().token,
            start_date,
            requested_to + timedelta(days=1),
        )
        now = datetime.now(timezone.utc).isoformat()
        with get_db_connection() as connection:
            for day in date_range(start_date, requested_to):
                payload = records_by_date.get(day, {})
                steps_record = payload.get("steps", {})
                active_record = payload.get("active-energy-burned", {})
                total_record = payload.get("total-calories", {})
                steps_value = _number(steps_record, "steps", "countSum")
                active_kcal = _number(
                    active_record,
                    "activeEnergyBurned",
                    "kcalSum",
                )
                total_kcal = _number(total_record, "totalCalories", "kcalSum")
                available_values = sum(
                    value is not None
                    for value in (steps_value, active_kcal, total_kcal)
                )

                if available_values:
                    execute(
                        connection,
                        """INSERT INTO google_health_daily_activity
                           (date, steps, active_energy_kcal, total_energy_kcal,
                            payload, fetched_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(date) DO UPDATE SET
                           steps=excluded.steps,
                           active_energy_kcal=excluded.active_energy_kcal,
                           total_energy_kcal=excluded.total_energy_kcal,
                           payload=excluded.payload,
                           fetched_at=excluded.fetched_at,
                           updated_at=excluded.updated_at""",
                        (
                            day.isoformat(),
                            int(steps_value) if steps_value is not None else None,
                            active_kcal,
                            total_kcal,
                            json_value(payload),
                            now,
                            now,
                        ),
                    )
                    stored_count += 1

                record_coverage(
                    connection,
                    source,
                    day,
                    "complete_data" if available_values else "complete_empty",
                    available_values,
                    run_id,
                )

        finish_sync_run(
            run_id,
            "success",
            fetched_count=fetched_count,
            stored_count=stored_count,
        )
        return stored_count
    except BaseException as error:
        finish_sync_run(
            run_id,
            "partial" if stored_count else "failed",
            fetched_count=fetched_count,
            stored_count=stored_count,
            error=error,
        )
        raise


def replicate_daily(days_back: int = 7) -> int:
    """Store Google steps and energy for the latest completed days."""
    if days_back < 1:
        raise ValueError("days_back must be at least 1")

    today = date.today()
    return _replicate_range(
        "google-health-daily",
        "google-health-daily",
        today - timedelta(days=days_back),
        today - timedelta(days=1),
    )


def replicate_today() -> int:
    """Store a replaceable, provisional snapshot for the current civil day."""
    today = date.today()
    return _replicate_range(
        "google-health-today",
        "google-health-today",
        today,
        today,
    )
