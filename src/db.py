"""Database utilities and connection management."""
import logging
import os
import sqlite3
import json
import re
import datetime as dt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

def is_running_in_docker() -> bool:
    """Check if we are running inside a Docker container."""
    # 1. Standard Docker flag file
    if os.path.exists('/.dockerenv'):
        return True
    
    # 2. Check cgroups (Linux containers)
    try:
        if os.path.exists('/proc/self/cgroup'):
            with open('/proc/self/cgroup', 'rt', encoding='utf-8') as f:
                if 'docker' in f.read():
                    return True
    except Exception:
        pass
        
    return False


def get_db_type():
    """Get the database type, falling back to auto-detection if not specified."""
    env_db_type = os.getenv("DB_TYPE", "").lower().strip()
    if env_db_type in ("sqlite", "postgres"):
        return env_db_type
        
    # Auto-detect: Docker uses Postgres, local PC uses SQLite
    if is_running_in_docker():
        return "postgres"
    else:
        return "sqlite"


class SQLiteCursorWrapper:
    """Wrapper around sqlite3.Cursor to make it behave like psycopg2 cursor."""

    def __init__(self, real_cursor):
        self.real_cursor = real_cursor

    def __getattr__(self, name):
        return getattr(self.real_cursor, name)

    def execute(self, sql, params=None):
        # 1. Map Postgres ALTER TABLE ... JSONB to SQLite equivalent
        if "ALTER TABLE" in sql and "IF NOT EXISTS" in sql:
            match = re.search(
                r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
                sql,
                re.IGNORECASE,
            )
            if match:
                table, col = match.groups()
                # Query table schema in SQLite
                self.real_cursor.execute(f"PRAGMA table_info({table})")
                cols = [row[1] for row in self.real_cursor.fetchall()]
                if col in cols:
                    # Column already exists, do nothing
                    return self
                else:
                    # SQLite supports ADD COLUMN. JSONB maps to TEXT
                    sql_alt = f"ALTER TABLE {table} ADD COLUMN {col} TEXT"
                    self.real_cursor.execute(sql_alt)
                    return self

        # 2. Map %s placeholders to ? style placeholders
        if params is not None:
            sql = sql.replace("%s", "?")
            
            # Map parameters (date objects, lists/dicts to json strings)
            adapted_params = []
            for p in params:
                if isinstance(p, (dt.date, dt.datetime)):
                    adapted_params.append(p.isoformat())
                elif isinstance(p, (dict, list)):
                    adapted_params.append(json.dumps(p))
                else:
                    adapted_params.append(p)
            params = tuple(adapted_params)

        if params is None:
            self.real_cursor.execute(sql)
        else:
            self.real_cursor.execute(sql, params)
        return self

    def fetchall(self):
        rows = self.real_cursor.fetchall()
        return [self._adapt_row(r) for r in rows]

    def fetchone(self):
        row = self.real_cursor.fetchone()
        if row is None:
            return None
        return self._adapt_row(row)

    def _adapt_row(self, row):
        """Try to deserialize JSON columns back to lists/dicts."""
        adapted_row = []
        for val in row:
            if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
                try:
                    adapted_row.append(json.loads(val))
                except Exception:
                    adapted_row.append(val)
            else:
                adapted_row.append(val)
        return tuple(adapted_row)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.real_cursor.close()


class SQLiteConnectionWrapper:
    """Wrapper around sqlite3.Connection to make it behave like psycopg2.Connection."""

    def __init__(self, real_conn):
        self.real_conn = real_conn

    def __getattr__(self, name):
        return getattr(self.real_conn, name)

    def cursor(self):
        return SQLiteCursorWrapper(self.real_conn.cursor())

    def __enter__(self):
        self.real_conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.real_conn.__exit__(exc_type, exc_val, exc_tb)


def init_sqlite_db(conn):
    """Initialize SQLite database schemas and views if they don't exist."""
    cursor = conn.cursor()
    
    # 1. Create raw_mfp table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_mfp (
            date TEXT PRIMARY KEY,
            meals_detail TEXT NOT NULL,
            calories_in INTEGER,
            protein NUMERIC,
            carbs NUMERIC,
            fat NUMERIC,
            sodium NUMERIC,
            sugar NUMERIC,
            fetched_at TEXT,
            updated_at TEXT
        );
    """)
    
    # 2. Create raw_intervals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_intervals (
            date TEXT PRIMARY KEY,
            calories_out INTEGER,
            distance_km FLOAT,
            elevation_gain INTEGER,
            workout_type TEXT,
            elapsed_time INTEGER,
            activities TEXT,
            updated_at TEXT
        );
    """)
    
    # 3. Create raw_fitbit table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_fitbit (
            date TEXT PRIMARY KEY,
            calories_out INTEGER,
            distance_km FLOAT,
            steps INTEGER,
            updated_at TEXT
        );
    """)
    
    # 4. Create daily_balance view
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS daily_balance AS
        SELECT
            d.date,
            m.calories_in,
            COALESCE(i.calories_out, f.calories_out, 0) AS calories_out,
            CASE
                WHEN i.date IS NOT NULL THEN 'intervals.icu'
                WHEN f.date IS NOT NULL THEN 'fitbit'
                ELSE NULL
            END AS calories_out_source,
            COALESCE(m.calories_in, 0) - COALESCE(i.calories_out, f.calories_out, 0) AS net_balance
        FROM (
            SELECT date FROM raw_mfp
            UNION
            SELECT date FROM raw_intervals
            UNION
            SELECT date FROM raw_fitbit
        ) d
        LEFT JOIN raw_mfp m ON m.date = d.date
        LEFT JOIN raw_intervals i ON i.date = d.date
        LEFT JOIN raw_fitbit f ON f.date = d.date
        ORDER BY d.date;
    """)
    
    conn.commit()
    cursor.close()


def get_db_connection():
    """Create a database connection based on DB_TYPE environment variable."""
    if get_db_type() == "sqlite":
        db_path = os.getenv("SQLITE_DB_PATH", "kaloriekassen.db")
        # Ensure target directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        logger.debug("Connecting to SQLite database: %s", db_path)
        conn = sqlite3.connect(db_path)
        # Initialize tables
        init_sqlite_db(conn)
        return SQLiteConnectionWrapper(conn)
    else:
        # Import conditionally so psycopg2 is not required for purely SQLite setups
        import psycopg2
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "db"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "kaloriekassen"),
            user=os.getenv("DB_USER", "kalorie"),
            password=os.getenv("DB_PASSWORD", "kalorie"),
        )


def execute_values(cur, sql, values):
    """
    Database-agnostic batch upsert.
    Uses psycopg2.extras.execute_values if running on Postgres,
    otherwise emulates it for SQLite using multi-row INSERT with param flattening.
    """
    if not values:
        return

    # Check if this is an SQLite cursor
    is_sqlite = (
        isinstance(cur, SQLiteCursorWrapper)
        or type(cur).__name__ == "sqlite3.Cursor"
        or "sqlite3" in type(cur).__module__
    )

    if is_sqlite:
        real_cur = cur.real_cursor if hasattr(cur, "real_cursor") else cur
        num_cols = len(values[0])
        # Build SQLite placeholders (e.g., (?, ?), (?, ?))
        row_placeholder = "(" + ", ".join(["?"] * num_cols) + ")"
        placeholders = ", ".join([row_placeholder] * len(values))
        
        # Replace %s placeholder in the sql statement with the built multi-row placeholders
        sqlite_sql = sql.replace("%s", placeholders)
        # Postgres NOW() is emulated via SQLite's CURRENT_TIMESTAMP
        sqlite_sql = sqlite_sql.replace("NOW()", "CURRENT_TIMESTAMP")
        
        # Flatten and serialize parameters
        flat_values = []
        for val in values:
            for v in val:
                if isinstance(v, (dt.date, dt.datetime)):
                    flat_values.append(v.isoformat())
                elif isinstance(v, (dict, list)):
                    flat_values.append(json.dumps(v))
                else:
                    flat_values.append(v)
                    
        # Execute the query
        real_cur.execute(sqlite_sql, flat_values)
    else:
        from psycopg2.extras import execute_values as pg_execute_values
        pg_execute_values(cur, sql, values)
