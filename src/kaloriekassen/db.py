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

DEFAULT_PROFILE = {
    "profile_id": "default",
    "height_cm": 185.0,
    "birth_date": "1986-09-02",
    "sex_for_bmr": "male",
    "default_weight_kg": 114.0,
    "timezone": "Europe/Copenhagen",
}

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
CREATE TABLE IF NOT EXISTS google_health_daily_activity (
    date TEXT PRIMARY KEY, steps INTEGER, active_energy_kcal REAL,
    total_energy_kcal REAL, payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_profile (
    profile_id TEXT PRIMARY KEY, height_cm REAL, birth_date TEXT,
    sex_for_bmr TEXT, default_weight_kg REAL,
    timezone TEXT NOT NULL DEFAULT 'Europe/Copenhagen',
    walking_stride_factor REAL NOT NULL DEFAULT 0.415,
    walking_kcal_per_kg_km REAL NOT NULL DEFAULT 0.5,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS body_measurements (
    measurement_id TEXT PRIMARY KEY, measured_at TEXT NOT NULL,
    weight_kg REAL, body_fat_pct REAL, fat_mass_kg REAL,
    fat_free_mass_kg REAL, source TEXT NOT NULL, source_id TEXT,
    payload TEXT NOT NULL, fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_body_measurements_measured_at
ON body_measurements(measured_at);
CREATE TABLE IF NOT EXISTS sync_runs (
    run_id TEXT PRIMARY KEY, job TEXT NOT NULL, source TEXT NOT NULL,
    requested_from TEXT, requested_to TEXT, status TEXT NOT NULL,
    fetched_count INTEGER NOT NULL DEFAULT 0, stored_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL, completed_at TEXT, error_type TEXT, error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_sync_runs_job_started
ON sync_runs(job, started_at);
CREATE TABLE IF NOT EXISTS sync_coverage (
    source TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0, last_successful_run_id TEXT,
    checked_at TEXT NOT NULL,
    PRIMARY KEY (source, date),
    FOREIGN KEY (last_successful_run_id) REFERENCES sync_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_sync_coverage_source_status_date
ON sync_coverage(source, status, date);
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
DROP VIEW IF EXISTS daily_energy_summary;
CREATE VIEW daily_energy_summary AS
WITH dates AS (
    SELECT date FROM raw_mfp
    UNION SELECT substr(started_at, 1, 10) FROM raw_intervals
    UNION SELECT date FROM google_health_daily_activity
    UNION SELECT substr(measured_at, 1, 10) FROM body_measurements
), exercise AS (
    SELECT substr(started_at, 1, 10) AS date, SUM(calories_out) AS calories_out
    FROM raw_intervals GROUP BY substr(started_at, 1, 10)
)
SELECT dates.date,
       CASE WHEN r.date IS NULL THEN NULL ELSE COALESCE(n.calories_in, 0) END AS calories_in,
       CASE
           WHEN COALESCE(b.weight_kg, p.default_weight_kg) IS NOT NULL
                AND p.height_cm IS NOT NULL
                AND p.birth_date IS NOT NULL
                AND p.sex_for_bmr IN ('male', 'female')
           THEN 10 * COALESCE(b.weight_kg, p.default_weight_kg)
                + 6.25 * p.height_cm
                - 5 * (
                    CAST(substr(dates.date, 1, 4) AS INTEGER)
                    - CAST(substr(p.birth_date, 1, 4) AS INTEGER)
                    - CASE
                        WHEN substr(dates.date, 6, 5) < substr(p.birth_date, 6, 5)
                        THEN 1 ELSE 0
                      END
                  )
                + CASE WHEN p.sex_for_bmr = 'male' THEN 5 ELSE -161 END
       END AS basal_energy_kcal,
       g.steps,
       CASE
           WHEN g.steps IS NOT NULL
                AND COALESCE(b.weight_kg, p.default_weight_kg) IS NOT NULL
                AND p.height_cm IS NOT NULL
           THEN g.steps * (p.height_cm / 100.0) * p.walking_stride_factor / 1000.0
                * COALESCE(b.weight_kg, p.default_weight_kg)
                * p.walking_kcal_per_kg_km
       END AS step_energy_estimated_kcal,
       COALESCE(e.calories_out, 0) AS exercise_energy_kcal,
       g.active_energy_kcal,
       g.total_energy_kcal AS estimated_tdee_kcal,
       CASE
           WHEN r.date IS NOT NULL AND g.total_energy_kcal IS NOT NULL
           THEN COALESCE(n.calories_in, 0) - g.total_energy_kcal
       END AS estimated_energy_balance_kcal,
       COALESCE(b.weight_kg, p.default_weight_kg) AS weight_kg,
       b.body_fat_pct,
       CASE WHEN g.total_energy_kcal IS NOT NULL THEN 'google_total_calories' END AS energy_model,
       CASE
           WHEN r.date IS NOT NULL AND g.total_energy_kcal IS NOT NULL THEN 'complete'
           WHEN r.date IS NULL AND g.total_energy_kcal IS NULL THEN 'missing_intake_and_expenditure'
           WHEN r.date IS NULL THEN 'missing_intake'
           ELSE 'missing_expenditure'
       END AS data_completeness
FROM dates
LEFT JOIN raw_mfp r ON r.date = dates.date
LEFT JOIN daily_nutrition n ON n.date = dates.date
LEFT JOIN google_health_daily_activity g ON g.date = dates.date
LEFT JOIN exercise e ON e.date = dates.date
LEFT JOIN user_profile p ON p.profile_id = 'default'
LEFT JOIN body_measurements b ON b.measurement_id = (
    SELECT b2.measurement_id FROM body_measurements b2
    WHERE substr(b2.measured_at, 1, 10) <= dates.date
      AND b2.weight_kg IS NOT NULL
    ORDER BY b2.measured_at DESC LIMIT 1
);
"""

POSTGRES_SCHEMA = SQLITE_SCHEMA.replace(
    "CREATE VIEW IF NOT EXISTS", "CREATE OR REPLACE VIEW"
).replace(
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
    connection.execute("""CREATE TABLE IF NOT EXISTS user_profile (
        profile_id TEXT PRIMARY KEY, height_cm REAL, birth_date TEXT,
        sex_for_bmr TEXT, default_weight_kg REAL,
        timezone TEXT NOT NULL DEFAULT 'Europe/Copenhagen',
        walking_stride_factor REAL NOT NULL DEFAULT 0.415,
        walking_kcal_per_kg_km REAL NOT NULL DEFAULT 0.5,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    profile_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(user_profile)").fetchall()
    }
    if "default_weight_kg" not in profile_columns:
        connection.execute("ALTER TABLE user_profile ADD COLUMN default_weight_kg REAL")
    connection.executescript(SQLITE_SCHEMA)
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(raw_mfp)").fetchall()
    }
    for column in LEGACY_RAW_MFP_TOTAL_COLUMNS:
        if column in existing_columns:
            connection.execute(f"ALTER TABLE raw_mfp DROP COLUMN {column}")
    connection.execute(
        """INSERT INTO user_profile
           (profile_id, height_cm, birth_date, sex_for_bmr, default_weight_kg,
            timezone, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(profile_id) DO UPDATE SET
           height_cm=COALESCE(user_profile.height_cm, excluded.height_cm),
           birth_date=COALESCE(user_profile.birth_date, excluded.birth_date),
           sex_for_bmr=COALESCE(user_profile.sex_for_bmr, excluded.sex_for_bmr),
           default_weight_kg=COALESCE(
               user_profile.default_weight_kg,
               excluded.default_weight_kg
           )""",
        tuple(DEFAULT_PROFILE.values()),
    )
    return connection


def _create_postgres_connection():
    import psycopg2

    connection = psycopg2.connect(
        host=os.getenv("DB_HOST", "db"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "kaloriekassen"), user=os.getenv("DB_USER", "kalorie"),
        password=os.getenv("DB_PASSWORD", "kalorie"),
    )
    with connection.cursor() as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS user_profile (
            profile_id TEXT PRIMARY KEY, height_cm REAL, birth_date TEXT,
            sex_for_bmr TEXT, default_weight_kg REAL,
            timezone TEXT NOT NULL DEFAULT 'Europe/Copenhagen',
            walking_stride_factor REAL NOT NULL DEFAULT 0.415,
            walking_kcal_per_kg_km REAL NOT NULL DEFAULT 0.5,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        cursor.execute(
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS default_weight_kg REAL"
        )
        for statement in POSTGRES_SCHEMA.split(";"):
            if statement.strip():
                cursor.execute(statement)
        for column in LEGACY_RAW_MFP_TOTAL_COLUMNS:
            cursor.execute(f'ALTER TABLE raw_mfp DROP COLUMN IF EXISTS "{column}"')
        cursor.execute(
            """INSERT INTO user_profile
               (profile_id, height_cm, birth_date, sex_for_bmr,
                default_weight_kg, timezone, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
               ON CONFLICT(profile_id) DO UPDATE SET
               height_cm=COALESCE(user_profile.height_cm, excluded.height_cm),
               birth_date=COALESCE(user_profile.birth_date, excluded.birth_date),
               sex_for_bmr=COALESCE(user_profile.sex_for_bmr, excluded.sex_for_bmr),
               default_weight_kg=COALESCE(
                   user_profile.default_weight_kg,
                   excluded.default_weight_kg
               )""",
            tuple(DEFAULT_PROFILE.values()),
        )
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
