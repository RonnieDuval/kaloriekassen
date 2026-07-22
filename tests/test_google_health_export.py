from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from kaloriekassen.db import execute, get_db_connection, json_value
from kaloriekassen.google_health import export as export_module


def _activity(activity_id: str, started_at: datetime) -> dict:
    return {
        "id": activity_id,
        "start_date_local": started_at.isoformat(timespec="seconds"),
        "type": "Ride",
        "elapsed_time": 3600,
        "distance": 25_000,
        "calories": 800,
    }


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
        return {"successful": [start_time[:10]], "failed": [], "total": 1}

    monkeypatch.setattr(export_module, "upload_exercise_records", upload)

    assert export_module.export(7) == 2
    assert uploaded_ids == [
        newest["start_date_local"] + "+02:00",
        boundary["start_date_local"] + "+02:00",
    ]

    with get_db_connection() as conn:
        exported = execute(
            conn,
            "SELECT intervals_activity_id FROM google_health_exports ORDER BY intervals_activity_id",
        ).fetchall()
    assert exported == [("boundary",), ("newest",)]


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
        return {"successful": ["today"], "failed": [], "total": 1}

    monkeypatch.setattr(export_module, "upload_exercise_records", upload)

    with pytest.raises(KeyboardInterrupt):
        export_module.export(7)

    with get_db_connection() as conn:
        exported = execute(
            conn,
            "SELECT intervals_activity_id, status FROM google_health_exports",
        ).fetchall()
    assert exported == [("newer", "sent")]
