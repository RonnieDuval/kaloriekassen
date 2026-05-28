"""Tests for the SQLite hybrid backend support."""
import os
import sqlite3
import datetime as dt
from unittest.mock import patch
import pytest

from src.db import get_db_connection, execute_values, SQLiteConnectionWrapper, SQLiteCursorWrapper


def test_sqlite_connection_management(tmp_path):
    """Test that SQLite connection and schema initialization works correctly."""
    db_file = tmp_path / "test_kalorie.db"
    
    with patch.dict(os.environ, {"DB_TYPE": "sqlite", "SQLITE_DB_PATH": str(db_file)}):
        # Trigger connection which will initialize schemas
        conn = get_db_connection()
        assert isinstance(conn, SQLiteConnectionWrapper)
        
        # Verify tables exist
        with conn.cursor() as cur:
            assert isinstance(cur, SQLiteCursorWrapper)
            
            # Check tables in sqlite
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            assert "raw_mfp" in tables
            assert "raw_intervals" in tables
            assert "raw_fitbit" in tables
            
            # Check view
            cur.execute("SELECT name FROM sqlite_master WHERE type='view'")
            views = [row[0] for row in cur.fetchall()]
            assert "daily_balance" in views
            
        conn.close()


def test_sqlite_cursor_wrapper_adaptations(tmp_path):
    """Test parameter adaptation, JSON serialization, and automatic deserialization."""
    db_file = tmp_path / "test_kalorie.db"
    
    with patch.dict(os.environ, {"DB_TYPE": "sqlite", "SQLITE_DB_PATH": str(db_file)}):
        conn = get_db_connection()
        
        today = dt.date(2026, 5, 27)
        test_meals = {
            "Breakfast": [{"name": "Oatmeal", "calories": 300}],
            "Lunch": []
        }
        
        with conn.cursor() as cur:
            # Test %s mapping and JSON serialization during insert
            cur.execute(
                "INSERT INTO raw_mfp (date, meals_detail, calories_in) VALUES (%s, %s, %s)",
                (today, test_meals, 300)
            )
            
            # Commit via connection
            conn.commit()
            
            # Test selection and automatic deserialization back to dicts/lists
            cur.execute("SELECT date, meals_detail, calories_in FROM raw_mfp WHERE date = %s", (today,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "2026-05-27"  # SQLite stores date as string ISO format
            assert isinstance(row[1], dict)  # Automatically parsed from JSON text!
            assert row[1]["Breakfast"][0]["name"] == "Oatmeal"
            assert row[2] == 300
            
        conn.close()


def test_sqlite_execute_values_emulation(tmp_path):
    """Test that the custom execute_values emulates bulk upserts on SQLite."""
    db_file = tmp_path / "test_kalorie.db"
    
    with patch.dict(os.environ, {"DB_TYPE": "sqlite", "SQLITE_DB_PATH": str(db_file)}):
        conn = get_db_connection()
        
        rows = [
            ("2026-05-25", 2500, 10.5, 200, "Run", 3600, '[]'),
            ("2026-05-26", 2800, 15.2, 350, "Ride", 5400, '[]'),
        ]
        
        sql = """
            INSERT INTO raw_intervals (date, calories_out, distance_km, elevation_gain, workout_type, elapsed_time, activities)
            VALUES %s
            ON CONFLICT (date) DO UPDATE SET
                calories_out = EXCLUDED.calories_out,
                distance_km = EXCLUDED.distance_km,
                workout_type = EXCLUDED.workout_type,
                updated_at = NOW();
        """
        
        with conn.cursor() as cur:
            execute_values(cur, sql, rows)
            conn.commit()
            
            # Query back and verify both inserted
            cur.execute("SELECT date, calories_out, workout_type FROM raw_intervals ORDER BY date ASC")
            results = cur.fetchall()
            assert len(results) == 2
            assert results[0][0] == "2026-05-25"
            assert results[0][1] == 2500
            assert results[0][2] == "Run"
            
            assert results[1][0] == "2026-05-26"
            assert results[1][1] == 2800
            assert results[1][2] == "Ride"
            
        conn.close()


def test_sqlite_alter_table_mapping(tmp_path):
    """Test that SQLite ALTER TABLE mapping intercepts JSONB column addition."""
    db_file = tmp_path / "test_kalorie.db"
    
    with patch.dict(os.environ, {"DB_TYPE": "sqlite", "SQLITE_DB_PATH": str(db_file)}):
        conn = get_db_connection()
        
        with conn.cursor() as cur:
            # Should run without error and be intercepted/noop since 'activities' already exists
            cur.execute("ALTER TABLE raw_intervals ADD COLUMN IF NOT EXISTS activities JSONB;")
            
            # Test on a custom table to check actual column appending
            cur.execute("CREATE TABLE test_alter (id INTEGER PRIMARY KEY);")
            cur.execute("ALTER TABLE test_alter ADD COLUMN IF NOT EXISTS extra_col JSONB;")
            
            # Verify the column exists and can be written to
            cur.execute("PRAGMA table_info(test_alter)")
            cols = [row[1] for row in cur.fetchall()]
            assert "extra_col" in cols
            
        conn.close()


def test_sqlite_auto_detection():
    """Test that database backend is auto-detected based on Docker environment."""
    from src.db import get_db_type, is_running_in_docker
    
    # 1. When DB_TYPE is set explicitly
    with patch.dict(os.environ, {"DB_TYPE": "sqlite"}):
        assert get_db_type() == "sqlite"
    with patch.dict(os.environ, {"DB_TYPE": "postgres"}):
        assert get_db_type() == "postgres"
        
    # 2. When DB_TYPE is empty/unset, it auto-detects
    with patch.dict(os.environ, {"DB_TYPE": ""}):
        with patch("src.db.is_running_in_docker", return_value=True):
            assert get_db_type() == "postgres"
        with patch("src.db.is_running_in_docker", return_value=False):
            assert get_db_type() == "sqlite"

