"""Database selection, connections, and schema setup.

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
    date TEXT PRIMARY KEY, meals_detail TEXT NOT NULL, calories_in INTEGER,
    protein REAL, carbs REAL, fat REAL, sodium REAL, sugar REAL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS raw_google_health_exercises (
    google_health_id TEXT PRIMARY KEY, start_time TEXT, end_time TEXT, exercise_type TEXT,
    payload TEXT NOT NULL, fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS google_health_exports (
    intervals_activity_id TEXT PRIMARY KEY, google_health_id TEXT, request_payload TEXT NOT NULL,
    status TEXT NOT NULL, last_error TEXT, attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, sent_at TEXT
);
CREATE VIEW IF NOT EXISTS daily_balance AS
SELECT m.date, m.calories_in, COALESCE(i.calories_out, 0) AS calories_out,
       m.calories_in - COALESCE(i.calories_out, 0) AS net_balance
FROM raw_mfp m LEFT JOIN (
    SELECT substr(started_at, 1, 10) AS date, SUM(calories_out) AS calories_out
    FROM raw_intervals GROUP BY substr(started_at, 1, 10)
) i ON i.date = m.date;
"""


POSTGRES_SCHEMA = SQLITE_SCHEMA.replace("TEXT", "TEXT").replace(
    "CREATE VIEW IF NOT EXISTS daily_balance AS", "CREATE OR REPLACE VIEW daily_balance AS"
).replace("substr(started_at, 1, 10)", "substring(started_at from 1 for 10)")


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
