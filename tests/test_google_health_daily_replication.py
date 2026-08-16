from datetime import date
from types import SimpleNamespace
import pytest

from kaloriekassen.db import get_db_connection
from kaloriekassen.google_health import daily_replication


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 8, 15)


def _rollup(day: int, value_name: str, value: dict):
    return {
        "civilStartTime": {
            "date": {"year": 2026, "month": 8, "day": day},
        },
        value_name: value,
    }


def test_replicates_daily_energy_and_builds_energy_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "daily-energy.db"))
    monkeypatch.setattr(daily_replication, "date", FixedDate)
    monkeypatch.setattr(
        daily_replication,
        "get_credentials",
        lambda: SimpleNamespace(token="token"),
    )
    records = {
        FixedDate(2026, 8, 14): {
            "steps": _rollup(14, "steps", {"countSum": "4000"}),
            "active-energy-burned": _rollup(
                14,
                "activeEnergyBurned",
                {"kcalSum": 800},
            ),
            "total-calories": _rollup(
                14,
                "totalCalories",
                {"kcalSum": 3000},
            ),
        }
    }
    monkeypatch.setattr(
        daily_replication,
        "_fetch_rollups",
        lambda _token, _start, _end: (records, 3),
    )

    assert daily_replication.replicate_daily(1) == 1

    with get_db_connection() as connection:
        connection.execute(
            """UPDATE user_profile SET height_cm = 180,
                      birth_date = '1986-09-02', sex_for_bmr = 'male',
                      default_weight_kg = 80
               WHERE profile_id = 'default'"""
        )
        connection.execute(
            """INSERT INTO body_measurements
               (measurement_id, measured_at, weight_kg, body_fat_pct, source,
                source_id, payload, fetched_at, updated_at)
               VALUES ('weight-1', '2026-08-14T07:00:00+02:00', 80, 20,
                       'withings', 'withings-1', '{}', 'now', 'now')"""
        )
        connection.execute(
            """INSERT INTO raw_mfp
               (date, meals_detail, fetched_at, updated_at)
               VALUES ('2026-08-14', '{}', 'now', 'now')"""
        )
        connection.execute(
            """INSERT INTO nutrition_entries
               (entry_id, date, meal_type, source_meal_name, position, food_name,
                calories, protein_g, carbs_g, fat_g, sodium_mg, sugar_g)
               VALUES ('food-1', '2026-08-14', 'dinner', 'Dinner', 0, 'Food',
                       2500, 0, 0, 0, 0, 0)"""
        )
        connection.execute(
            """INSERT INTO raw_intervals
               (activity_id, started_at, activity_type, calories_out,
                distance_meters, elevation_gain_meters, elapsed_time_seconds,
                payload)
               VALUES ('ride-1', '2026-08-14T17:00:00', 'Ride', 500,
                       20000, 100, 3600, '{}')"""
        )

        summary = connection.execute(
            """SELECT calories_in, basal_energy_kcal, steps,
                      step_energy_estimated_kcal, exercise_energy_kcal,
                      active_energy_kcal, estimated_tdee_kcal,
                      estimated_energy_balance_kcal,
                      weight_kg, body_fat_pct, energy_model, data_completeness
               FROM daily_energy_summary WHERE date = '2026-08-14'"""
        ).fetchone()
        coverage = connection.execute(
            """SELECT status, record_count FROM sync_coverage
               WHERE source = 'google-health-daily' AND date = '2026-08-14'"""
        ).fetchone()

    assert summary[:3] == (
        2500.0,
        1735.0,
        4000,
    )
    assert summary[3] == pytest.approx(119.52)
    assert summary[4:] == (
        500.0,
        800.0,
        3000.0,
        -500.0,
        80.0,
        20.0,
        "google_total_calories",
        "complete",
    )
    assert coverage == ("complete_data", 3)


def test_replicates_current_day_as_a_separate_provisional_job(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "today-energy.db"))
    monkeypatch.setattr(daily_replication, "date", FixedDate)
    monkeypatch.setattr(
        daily_replication,
        "get_credentials",
        lambda: SimpleNamespace(token="token"),
    )
    records = {
        FixedDate(2026, 8, 15): {
            "steps": _rollup(15, "steps", {"countSum": "1234"}),
            "active-energy-burned": _rollup(
                15,
                "activeEnergyBurned",
                {"kcalSum": 250},
            ),
            "total-calories": _rollup(
                15,
                "totalCalories",
                {"kcalSum": 1600},
            ),
        }
    }
    requested_ranges = []

    def fetch(_token, start, end):
        requested_ranges.append((start, end))
        return records, 3

    monkeypatch.setattr(daily_replication, "_fetch_rollups", fetch)

    assert daily_replication.replicate_today() == 1

    with get_db_connection() as connection:
        activity = connection.execute(
            """SELECT steps, active_energy_kcal, total_energy_kcal
               FROM google_health_daily_activity WHERE date = '2026-08-15'"""
        ).fetchone()
        run = connection.execute(
            """SELECT job, source, requested_from, requested_to, status
               FROM sync_runs ORDER BY started_at DESC LIMIT 1"""
        ).fetchone()

    assert requested_ranges == [
        (FixedDate(2026, 8, 15), FixedDate(2026, 8, 16))
    ]
    assert activity == (1234, 250.0, 1600.0)
    assert run == (
        "google-health-today",
        "google-health-today",
        "2026-08-15",
        "2026-08-15",
        "success",
    )
