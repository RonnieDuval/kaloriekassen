"""Read-only dashboard queries shared by the HTML page and JSON endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from kaloriekassen.db import execute, get_db_connection


def _rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _row(cursor: Any) -> dict[str, Any] | None:
    rows = _rows(cursor)
    return rows[0] if rows else None


def _latest_sync_runs(connection: Any) -> list[dict[str, Any]]:
    runs = _rows(
        execute(
            connection,
            """SELECT job, source, status, fetched_count, stored_count,
                      started_at, completed_at, error_type, error_message
               FROM sync_runs
               ORDER BY started_at DESC
               LIMIT 250""",
        )
    )
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        latest.setdefault(run["job"], run)
    return sorted(latest.values(), key=lambda item: item["job"])


def get_dashboard(days: int) -> dict[str, Any]:
    """Return the complete payload needed by the dashboard."""
    with get_db_connection() as connection:
        daily = _rows(
            execute(
                connection,
                """SELECT date, calories_in, basal_energy_kcal, steps,
                          step_energy_estimated_kcal, exercise_energy_kcal,
                          active_energy_kcal, estimated_tdee_kcal,
                          estimated_energy_balance_kcal, weight_kg,
                          body_fat_pct, energy_model, data_completeness
                   FROM daily_energy_summary
                   ORDER BY date DESC
                   LIMIT ?""",
                (days,),
            )
        )
        daily.reverse()

        measurement_cutoff = (date.today() - timedelta(days=max(days, 365))).isoformat()
        measurements = _rows(
            execute(
                connection,
                """SELECT measurement_id, measured_at, weight_kg, body_fat_pct,
                          fat_mass_kg, fat_free_mass_kg, source
                   FROM body_measurements
                   WHERE substr(measured_at, 1, 10) >= ?
                   ORDER BY measured_at""",
                (measurement_cutoff,),
            )
        )

        activities = _rows(
            execute(
                connection,
                """SELECT activity_id, started_at, activity_type, calories_out,
                          distance_meters, elevation_gain_meters,
                          elapsed_time_seconds
                   FROM raw_intervals
                   ORDER BY started_at DESC
                   LIMIT 12""",
            )
        )

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "days": days,
            "daily": daily,
            "measurements": measurements,
            "activities": activities,
            "sync_jobs": _latest_sync_runs(connection),
        }


def get_day(day: str) -> dict[str, Any] | None:
    """Return nutrition, exercise and measurement details for one civil day."""
    with get_db_connection() as connection:
        summary = _row(
            execute(
                connection,
                """SELECT date, calories_in, basal_energy_kcal, steps,
                          step_energy_estimated_kcal, exercise_energy_kcal,
                          active_energy_kcal, estimated_tdee_kcal,
                          estimated_energy_balance_kcal, weight_kg,
                          body_fat_pct, energy_model, data_completeness
                   FROM daily_energy_summary WHERE date = ?""",
                (day,),
            )
        )
        entries = _rows(
            execute(
                connection,
                """SELECT meal_type, source_meal_name, position, food_name,
                          consumed_at, time_is_estimated, calories, protein_g,
                          carbs_g, fat_g, sodium_mg, sugar_g
                   FROM nutrition_entries
                   WHERE date = ?
                   ORDER BY meal_type, source_meal_name, position""",
                (day,),
            )
        )
        activities = _rows(
            execute(
                connection,
                """SELECT activity_id, started_at, activity_type, calories_out,
                          distance_meters, elevation_gain_meters,
                          elapsed_time_seconds
                   FROM raw_intervals
                   WHERE substr(started_at, 1, 10) = ?
                   ORDER BY started_at""",
                (day,),
            )
        )
        measurement = _row(
            execute(
                connection,
                """SELECT measurement_id, measured_at, weight_kg, body_fat_pct,
                          fat_mass_kg, fat_free_mass_kg, source
                   FROM body_measurements
                   WHERE substr(measured_at, 1, 10) <= ?
                   ORDER BY measured_at DESC
                   LIMIT 1""",
                (day,),
            )
        )
        if summary is None and not entries and not activities:
            return None
        return {
            "date": day,
            "summary": summary,
            "nutrition_entries": entries,
            "activities": activities,
            "measurement": measurement,
        }


def database_is_available() -> bool:
    """Return whether a simple database query succeeds."""
    try:
        with get_db_connection() as connection:
            return execute(connection, "SELECT 1").fetchone()[0] == 1
    except Exception:
        return False
