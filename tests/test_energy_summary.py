import sqlite3
import pytest

from kaloriekassen.db import get_db_connection


def test_default_profile_produces_stable_mifflin_st_jeor_bmr(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "energy.db"))

    with get_db_connection() as connection:
        profile = connection.execute(
            """SELECT height_cm, birth_date, sex_for_bmr, default_weight_kg
               FROM user_profile WHERE profile_id = 'default'"""
        ).fetchone()
        for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
            connection.execute(
                """INSERT INTO google_health_daily_activity
                   (date, steps, active_energy_kcal, total_energy_kcal, payload)
                   VALUES (?, 4000, 500, 3000, '{}')""",
                (day,),
            )
        energy_values = connection.execute(
            """SELECT date, basal_energy_kcal, step_energy_estimated_kcal
               FROM daily_energy_summary
               ORDER BY date"""
        ).fetchall()

    assert profile == (185.0, "1986-09-02", "male", 114.0)
    assert [row[:2] for row in energy_values] == [
        ("2026-09-01", 2106.25),
        ("2026-09-02", 2101.25),
        ("2026-09-03", 2101.25),
    ]
    assert all(row[2] == pytest.approx(175.047) for row in energy_values)


def test_existing_profile_table_gets_default_weight_migration(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy-profile.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE user_profile (
            profile_id TEXT PRIMARY KEY, height_cm REAL, birth_date TEXT,
            sex_for_bmr TEXT, timezone TEXT NOT NULL,
            walking_stride_factor REAL NOT NULL DEFAULT 0.415,
            walking_kcal_per_kg_km REAL NOT NULL DEFAULT 0.5,
            updated_at TEXT NOT NULL
        )""")

    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(database_path))
    with get_db_connection() as connection:
        columns = [
            row[1] for row in connection.execute("PRAGMA table_info(user_profile)")
        ]
        profile = connection.execute(
            "SELECT default_weight_kg FROM user_profile WHERE profile_id = 'default'"
        ).fetchone()

    assert "default_weight_kg" in columns
    assert profile == (114.0,)
