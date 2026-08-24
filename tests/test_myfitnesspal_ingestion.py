import json
import sqlite3
from datetime import date

from kaloriekassen.db import get_db_connection
from kaloriekassen.myfitnesspal import sync as myfitnesspal_sync


def _diary_day(foods):
    return {"date": "2026-07-20", "meals": {"Breakfast": foods}}


def test_ingest_stores_food_entries_and_exposes_aggregated_views(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "nutrition.db"))
    monkeypatch.setattr(
        myfitnesspal_sync,
        "hent_mfp_dag",
        lambda _day: _diary_day([
            {"name": "Oatmeal", "calories": 250, "carbohydrates": 42, "fat": 5,
             "protein": 8, "sodium": 10, "sugar": 2},
            {"name": "Milk", "calories": 100, "carbohydrates": 10, "fat": 4,
             "protein": 7, "sodium": 90, "sugar": 10},
        ]),
    )

    assert myfitnesspal_sync.ingest_range(date(2026, 7, 20), date(2026, 7, 20)) == 1

    with get_db_connection() as connection:
        entries = connection.execute(
            "SELECT meal_type, source_meal_name, position, food_name FROM nutrition_entries ORDER BY position"
        ).fetchall()
        meal_total = connection.execute(
            "SELECT food_count, calories, protein_g, sodium_mg FROM nutrition_meal_totals"
        ).fetchone()
        daily_total = connection.execute(
            "SELECT calories_in, carbs_g, fat_g, sugar_g FROM daily_nutrition"
        ).fetchone()
        daily_energy = connection.execute(
            """SELECT calories_in, exercise_energy_kcal,
                      estimated_energy_balance_kcal, data_completeness
               FROM daily_energy_summary"""
        ).fetchone()
        raw_meals = json.loads(connection.execute("SELECT meals_detail FROM raw_mfp").fetchone()[0])

    assert entries == [
        ("breakfast", "Breakfast", 0, "Oatmeal"),
        ("breakfast", "Breakfast", 1, "Milk"),
    ]
    assert meal_total == (2, 350.0, 15.0, 100.0)
    assert daily_total == (350.0, 52.0, 9.0, 12.0)
    assert daily_energy == (350.0, 0, None, "missing_expenditure")
    assert raw_meals["Breakfast"][0]["name"] == "Oatmeal"


def test_reingest_replaces_entries_for_the_day(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "nutrition.db"))
    returned_days = [_diary_day([
        {"name": "Old food", "calories": 100},
        {"name": "Removed food", "calories": 200},
    ])]
    monkeypatch.setattr(
        myfitnesspal_sync,
        "hent_mfp_dag",
        lambda _day: returned_days[0],
    )
    myfitnesspal_sync.ingest_range(date(2026, 7, 20), date(2026, 7, 20))
    returned_days[:] = [_diary_day([{"name": "Updated food", "calories": 300}])]

    myfitnesspal_sync.ingest_range(date(2026, 7, 20), date(2026, 7, 20))

    with get_db_connection() as connection:
        entries = connection.execute(
            "SELECT food_name, calories FROM nutrition_entries"
        ).fetchall()
    assert entries == [("Updated food", 300.0)]


def test_existing_raw_mfp_is_migrated_to_raw_columns_only(tmp_path, monkeypatch):
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE raw_mfp (
            date TEXT PRIMARY KEY, meals_detail TEXT NOT NULL, calories_in INTEGER,
            protein REAL, carbs REAL, fat REAL, sodium REAL, sugar REAL,
            fetched_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        connection.execute(
            "INSERT INTO raw_mfp VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-07-20", '{"Breakfast":[]}', 0, 0, 0, 0, 0, 0, "fetched", "updated"),
        )
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(database_path))

    with get_db_connection() as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(raw_mfp)")]
        raw_row = connection.execute("SELECT * FROM raw_mfp").fetchone()

    assert columns == ["date", "meals_detail", "fetched_at", "updated_at"]
    assert raw_row == ("2026-07-20", '{"Breakfast":[]}', "fetched", "updated")
