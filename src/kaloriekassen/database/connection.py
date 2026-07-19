"""Database connection and schema setup."""
import json
import os
import sqlite3
from contextlib import contextmanager


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_intervals (
    activity_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    activity_type TEXT,
    calories_out REAL,
    distance_meters REAL,
    elevation_gain_meters REAL,
    elapsed_time_seconds INTEGER,
    payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS raw_mfp (
    date TEXT PRIMARY KEY, meals_detail TEXT NOT NULL, calories_in INTEGER,
    protein REAL, carbs REAL, fat REAL, sodium REAL, sugar REAL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS raw_google_health_exercises (
    google_health_id TEXT PRIMARY KEY, start_time TEXT, end_time TEXT,
    exercise_type TEXT, payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS google_health_exports (
    intervals_activity_id TEXT PRIMARY KEY, google_health_id TEXT,
    request_payload TEXT NOT NULL, status TEXT NOT NULL, last_error TEXT,
    attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, sent_at TEXT
);
CREATE VIEW IF NOT EXISTS daily_balance AS
SELECT m.date, m.calories_in, COALESCE(i.calories_out, 0) AS calories_out,
       m.calories_in - COALESCE(i.calories_out, 0) AS net_balance
FROM raw_mfp m LEFT JOIN (
    SELECT substr(started_at, 1, 10) AS date, SUM(calories_out) AS calories_out
    FROM raw_intervals GROUP BY substr(started_at, 1, 10)
) i ON i.date = m.date;
"""


def get_db_type() -> str:
    return os.getenv("DB_TYPE", "sqlite").lower()


def _sqlite_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(os.getenv("SQLITE_DB_PATH", "kaloriekassen.db"))
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_SQL)
    return connection


@contextmanager
def get_db_connection():
    """Yield a database connection. SQLite is the supported local backend."""
    if get_db_type() != "sqlite":
        raise ValueError("Only DB_TYPE=sqlite is supported by the current schema")
    connection = _sqlite_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def json_value(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)
