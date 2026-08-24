from datetime import date

import pytest

from kaloriekassen.db import get_db_connection
from kaloriekassen.intervals import sync as intervals_sync
from kaloriekassen.myfitnesspal import sync as myfitnesspal_sync
from kaloriekassen.sync_tracking import (
    finish_sync_run,
    format_status_report,
    record_coverage,
    start_sync_run,
)


def _use_database(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "sync-tracking.db"))


def test_records_completed_run_coverage_and_status_report(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path)
    run_id = start_sync_run(
        "intervals", "intervals", date(2026, 8, 14), date(2026, 8, 15)
    )
    with get_db_connection() as connection:
        record_coverage(
            connection, "intervals", "2026-08-14", "complete_data", 2, run_id
        )
        record_coverage(
            connection, "intervals", "2026-08-15", "complete_empty", 0, run_id
        )
    finish_sync_run(run_id, "success", fetched_count=2, stored_count=2)

    with get_db_connection() as connection:
        run = connection.execute(
            """SELECT status, fetched_count, stored_count, completed_at
               FROM sync_runs WHERE run_id = ?""",
            (run_id,),
        ).fetchone()
        coverage = connection.execute(
            """SELECT date, status, record_count FROM sync_coverage
               ORDER BY date"""
        ).fetchall()

    assert run[:3] == ("success", 2, 2)
    assert run[3] is not None
    assert coverage == [
        ("2026-08-14", "complete_data", 2),
        ("2026-08-15", "complete_empty", 0),
    ]
    report = format_status_report()
    assert "intervals (intervals)" in report
    assert "Status: success" in report
    assert "Dækning til og med: 2026-08-15" in report
    assert "Fejlede dage: 0" in report


def test_error_message_redacts_known_secret(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path)
    monkeypatch.setenv("MFP_COOKIE_HEADER", "private-cookie-value")
    run_id = start_sync_run("myfitnesspal", "myfitnesspal")

    finish_sync_run(
        run_id,
        "failed",
        error=RuntimeError("Cookie: private-cookie-value was rejected"),
    )

    with get_db_connection() as connection:
        error_message = connection.execute(
            "SELECT error_message FROM sync_runs WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
    assert "private-cookie-value" not in error_message
    assert "[REDACTED]" in error_message


def test_intervals_marks_activity_and_rest_days(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path)
    monkeypatch.setenv("INTERVALS_API_KEY", "test-key")
    monkeypatch.setenv("INTERVALS_ATHLETE_ID", "test-athlete")
    monkeypatch.setattr(
        intervals_sync,
        "requested_date_range",
        lambda _days: (date(2026, 8, 14), date(2026, 8, 15)),
    )
    monkeypatch.setattr(
        intervals_sync.IntervalsFetcher,
        "fetch_raw",
        lambda _: [
            {
                "id": "ride-1",
                "start_date_local": "2026-08-14T10:00:00",
                "type": "Ride",
                "calories": 500,
                "distance": 20_000,
                "total_elevation_gain": 100,
                "elapsed_time": 3600,
            }
        ],
    )

    assert intervals_sync.ingest(2) == 1

    with get_db_connection() as connection:
        coverage = connection.execute(
            "SELECT date, status, record_count FROM sync_coverage ORDER BY date"
        ).fetchall()
    assert coverage == [
        ("2026-08-14", "complete_data", 1),
        ("2026-08-15", "complete_empty", 0),
    ]


def test_myfitnesspal_records_exact_range_with_empty_and_populated_days(
    tmp_path, monkeypatch
):
    _use_database(monkeypatch, tmp_path)
    days = {
        "2026-08-13": {"date": "2026-08-13", "meals": {}},
        "2026-08-14": {
            "date": "2026-08-14",
            "meals": {"Breakfast": [{"name": "Oatmeal", "calories": 250}]},
        },
    }
    monkeypatch.setattr(myfitnesspal_sync, "hent_mfp_dag", days.__getitem__)

    assert myfitnesspal_sync.ingest_range(
        date(2026, 8, 13), date(2026, 8, 14)
    ) == 2

    with get_db_connection() as connection:
        run_status = connection.execute(
            "SELECT status FROM sync_runs WHERE job = 'myfitnesspal'"
        ).fetchone()[0]
        coverage = connection.execute(
            "SELECT date, status, record_count FROM sync_coverage ORDER BY date"
        ).fetchall()
    assert run_status == "success"
    assert coverage == [
        ("2026-08-13", "complete_empty", 0),
        ("2026-08-14", "complete_data", 1),
    ]


def test_myfitnesspal_preserves_completed_days_when_later_fetch_fails(
    tmp_path, monkeypatch
):
    _use_database(monkeypatch, tmp_path)

    def fetch(day):
        if day == "2026-08-14":
            raise RuntimeError("source unavailable")
        return {"date": day, "meals": {}}

    monkeypatch.setattr(myfitnesspal_sync, "hent_mfp_dag", fetch)

    with pytest.raises(RuntimeError, match="source unavailable"):
        myfitnesspal_sync.ingest_range(date(2026, 8, 13), date(2026, 8, 15))

    with get_db_connection() as connection:
        stored_days = connection.execute("SELECT date FROM raw_mfp ORDER BY date").fetchall()
        run = connection.execute(
            "SELECT status, fetched_count, stored_count FROM sync_runs"
        ).fetchone()
        coverage = connection.execute(
            "SELECT date, status FROM sync_coverage ORDER BY date"
        ).fetchall()

    assert stored_days == [("2026-08-13",)]
    assert run == ("partial", 1, 1)
    assert coverage == [
        ("2026-08-13", "complete_empty"),
        ("2026-08-14", "failed"),
        ("2026-08-15", "failed"),
    ]


def test_failed_fetch_records_failed_run_and_coverage(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path)
    monkeypatch.setenv("INTERVALS_API_KEY", "test-key")
    monkeypatch.setenv("INTERVALS_ATHLETE_ID", "test-athlete")
    monkeypatch.setattr(
        intervals_sync,
        "requested_date_range",
        lambda _days: (date(2026, 8, 15), date(2026, 8, 15)),
    )

    def fail_fetch(_fetcher):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(intervals_sync.IntervalsFetcher, "fetch_raw", fail_fetch)

    with pytest.raises(RuntimeError, match="source unavailable"):
        intervals_sync.ingest(1)

    with get_db_connection() as connection:
        run = connection.execute(
            "SELECT status, error_type, error_message FROM sync_runs"
        ).fetchone()
        coverage = connection.execute(
            "SELECT date, status FROM sync_coverage"
        ).fetchone()
    assert run == ("failed", "RuntimeError", "source unavailable")
    assert coverage == ("2026-08-15", "failed")
