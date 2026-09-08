from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.google_health import export as export_module


COPENHAGEN = ZoneInfo("Europe/Copenhagen")


def _activity(activity_id: str, started_at: datetime) -> dict:
    local_start = started_at.replace(tzinfo=COPENHAGEN)
    return {
        "id": activity_id,
        "start_date": (
            local_start.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        "start_date_local": started_at.isoformat(timespec="seconds"),
        "timezone": "Europe/Copenhagen",
        "type": "Ride",
        "elapsed_time": 3600,
        "distance": 25_000,
        "calories": 800,
    }


def _expected_google_start(activity: dict) -> str:
    utc_start = datetime.fromisoformat(
        activity["start_date"].replace("Z", "+00:00")
    )
    return utc_start.astimezone(COPENHAGEN).isoformat()


def _insert_activity(activity: dict) -> None:
    with get_db_connection() as conn:
        execute(
            conn,
            """INSERT INTO raw_intervals
               (activity_id, started_at, payload)
               VALUES (?, ?, ?)""",
            (
                activity["id"],
                activity["start_date_local"],
                json_value(activity),
            ),
        )


def test_export_only_processes_requested_period_newest_first(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "export.db"))
    monkeypatch.setattr(
        export_module, "get_credentials", lambda: SimpleNamespace(token="token")
    )

    today = date.today()
    newest = _activity("newest", datetime.combine(today, datetime.min.time()).replace(hour=18))
    boundary = _activity(
        "boundary",
        datetime.combine(today - timedelta(days=6), datetime.min.time()).replace(hour=8),
    )
    too_old = _activity(
        "too-old",
        datetime.combine(today - timedelta(days=7), datetime.min.time()).replace(hour=8),
    )
    for activity in (boundary, too_old, newest):
        _insert_activity(activity)

    uploaded_ids = []

    def upload(_token, records):
        start_time = records[0]["exercise"]["interval"]["startTime"]
        uploaded_ids.append(start_time)
        return {
            "successful": [{
                "date": start_time[:10],
                "google_health_id": f"google/{start_time}",
            }],
            "failed": [],
            "total": 1,
        }

    monkeypatch.setattr(export_module, "upload_exercise_records", upload)

    assert export_module.export(7) == 2
    assert uploaded_ids == [
        _expected_google_start(newest),
        _expected_google_start(boundary),
    ]

    with get_db_connection() as conn:
        exported = execute(
            conn,
            """SELECT intervals_activity_id, google_health_id
               FROM google_health_exports ORDER BY intervals_activity_id""",
        ).fetchall()
        sync_run = execute(
            conn,
            """SELECT status, fetched_count, stored_count FROM sync_runs
               WHERE job = 'google-health-export'""",
        ).fetchone()
    assert exported == [
        ("boundary", f"google/{_expected_google_start(boundary)}"),
        ("newest", f"google/{_expected_google_start(newest)}"),
    ]
    assert sync_run == ("success", 2, 2)


def test_completed_exports_survive_an_interrupted_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "interrupted.db"))
    monkeypatch.setattr(
        export_module, "get_credentials", lambda: SimpleNamespace(token="token")
    )

    today = date.today()
    _insert_activity(_activity("older", datetime.combine(today, datetime.min.time()).replace(hour=8)))
    _insert_activity(_activity("newer", datetime.combine(today, datetime.min.time()).replace(hour=18)))

    calls = 0

    def upload(_token, records):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return {
            "successful": [{
                "date": "today",
                "google_health_id": "google/newer",
            }],
            "failed": [],
            "total": 1,
        }

    monkeypatch.setattr(export_module, "upload_exercise_records", upload)

    with pytest.raises(KeyboardInterrupt):
        export_module.export(7)

    with get_db_connection() as conn:
        exported = execute(
            conn,
            """SELECT intervals_activity_id, google_health_id, status
               FROM google_health_exports""",
        ).fetchall()
        sync_run = execute(
            conn,
            """SELECT status, fetched_count, stored_count, error_type
               FROM sync_runs WHERE job = 'google-health-export'""",
        ).fetchone()
    assert exported == [("newer", "google/newer", "sent")]
    assert sync_run == ("partial", 2, 1, "KeyboardInterrupt")


def test_empty_export_finishes_without_nested_sqlite_writer(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "empty-export.db"))

    def credentials_must_not_be_needed():
        raise AssertionError("No Google credentials should be loaded for an empty export")

    monkeypatch.setattr(
        export_module,
        "get_credentials",
        credentials_must_not_be_needed,
    )

    assert export_module.export(3) == 0

    with get_db_connection() as connection:
        sync_run = execute(
            connection,
            """SELECT status, fetched_count, stored_count, error_type
               FROM sync_runs WHERE job = 'google-health-export'""",
        ).fetchone()

    assert sync_run == ("success", 0, 0, None)
