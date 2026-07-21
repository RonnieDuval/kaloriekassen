"""Database selection, connections, schema setup, and migrations.

The default is intentional: a local process uses SQLite, while a container uses
PostgreSQL. Set ``DB_TYPE`` to ``sqlite`` or ``postgres`` to override it.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any

from dotenv import load_dotenv

load_dotenv()

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_intervals (
    activity_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, activity_type TEXT,
    calories_out REAL, distance_meters REAL, elevation_gain_meters REAL,
    elapsed_time_seconds INTEGER, payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS raw_mfp (
    date TEXT PRIMARY KEY, meals_detail TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS nutrition_entries (
    entry_id TEXT PRIMARY KEY, date TEXT NOT NULL, meal_type TEXT NOT NULL,
    source_meal_name TEXT NOT NULL, position INTEGER NOT NULL, food_name TEXT NOT NULL,
    consumed_at TEXT, time_is_estimated INTEGER NOT NULL DEFAULT 0,
    calories REAL NOT NULL, protein_g REAL NOT NULL, carbs_g REAL NOT NULL,
    fat_g REAL NOT NULL, sodium_mg REAL NOT NULL, sugar_g REAL NOT NULL,
    UNIQUE (date, source_meal_name, position),
    FOREIGN KEY (date) REFERENCES raw_mfp(date) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_nutrition_entries_date_meal
ON nutrition_entries(date, meal_type);
CREATE TABLE IF NOT EXISTS raw_google_health_exercises (
    google_health_id TEXT PRIMARY KEY, start_time TEXT, end_time TEXT, exercise_type TEXT,
    payload TEXT NOT NULL, fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS google_health_exports (
    intervals_activity_id TEXT PRIMARY KEY, google_health_id TEXT, request_payload TEXT NOT NULL,
    status TEXT NOT NULL, last_error TEXT, attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, sent_at TEXT
);
CREATE VIEW IF NOT EXISTS nutrition_meal_totals AS
SELECT date, meal_type, source_meal_name, COUNT(*) AS food_count,
       SUM(calories) AS calories, SUM(protein_g) AS protein_g,
       SUM(carbs_g) AS carbs_g, SUM(fat_g) AS fat_g,
       SUM(sodium_mg) AS sodium_mg, SUM(sugar_g) AS sugar_g
FROM nutrition_entries
GROUP BY date, meal_type, source_meal_name;
CREATE VIEW IF NOT EXISTS daily_nutrition AS
SELECT date, SUM(calories) AS calories_in, SUM(protein_g) AS protein_g,
       SUM(carbs_g) AS carbs_g, SUM(fat_g) AS fat_g,
       SUM(sodium_mg) AS sodium_mg, SUM(sugar_g) AS sugar_g
FROM nutrition_entries GROUP BY date;
DROP VIEW IF EXISTS daily_balance;
CREATE VIEW daily_balance AS
SELECT r.date, COALESCE(d.calories_in, 0) AS calories_in,
       COALESCE(i.calories_out, 0) AS calories_out,
       COALESCE(d.calories_in, 0) - COALESCE(i.calories_out, 0) AS net_balance
FROM raw_mfp r
LEFT JOIN daily_nutrition d ON d.date = r.date
LEFT JOIN (
    SELECT substr(started_at, 1, 10) AS date, SUM(calories_out) AS calories_out
    FROM raw_intervals GROUP BY substr(started_at, 1, 10)
) i ON i.date = r.date;
"""

POSTGRES_SCHEMA = SQLITE_SCHEMA.replace(
    "substr(started_at, 1, 10)", "substring(started_at from 1 for 10)"
)

LEGACY_RAW_MFP_TOTAL_COLUMNS = (
    "calories_in",
    "protein",
    "carbs",
    "fat",
    "sodium",
    "sugar",
)


def is_running_in_container() -> bool:
    """Return whether the current process appears to run in a container."""
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup", encoding="utf-8") as cgroup:
            return any(marker in cgroup.read() for marker in ("docker", "containerd", "kubepods"))
    except OSError:
        return False


def get_db_type() -> str:
    configured = os.getenv("DB_TYPE", "").strip().lower()
    if configured:
        if configured not in {"sqlite", "postgres"}:
            raise ValueError("DB_TYPE must be either 'sqlite' or 'postgres'")
        return configured
    return "postgres" if is_running_in_container() else "sqlite"


def _create_sqlite_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(os.getenv("SQLITE_DB_PATH", "kaloriekassen.db"))
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SQLITE_SCHEMA)
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(raw_mfp)").fetchall()
    }
    for column in LEGACY_RAW_MFP_TOTAL_COLUMNS:
        if column in existing_columns:
            connection.execute(f"ALTER TABLE raw_mfp DROP COLUMN {column}")
    return connection


def _create_postgres_connection():
    import psycopg2

    connection = psycopg2.connect(
        host=os.getenv("DB_HOST", "db"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "kaloriekassen"), user=os.getenv("DB_USER", "kalorie"),
        password=os.getenv("DB_PASSWORD", "kalorie"),
    )
    with connection.cursor() as cursor:
        for statement in POSTGRES_SCHEMA.split(";"):
            if statement.strip():
                cursor.execute(statement)
        for column in LEGACY_RAW_MFP_TOTAL_COLUMNS:
            cursor.execute(f'ALTER TABLE raw_mfp DROP COLUMN IF EXISTS "{column}"')
    connection.commit()
    return connection


@contextmanager
def get_db_connection():
    """Yield an initialized SQLite or PostgreSQL connection."""
    connection = _create_postgres_connection() if get_db_type() == "postgres" else _create_sqlite_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def execute(connection: Any, sql: str, parameters: tuple = ()):
    """Execute portable SQL and return a cursor suitable for fetching rows."""
    if get_db_type() == "sqlite":
        return connection.execute(sql, parameters)
    cursor = connection.cursor()
    cursor.execute(sql.replace("?", "%s"), parameters)
    return cursor


def json_value(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)
