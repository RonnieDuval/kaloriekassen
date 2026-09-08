import json
from types import SimpleNamespace
from datetime import date

from kaloriekassen.db import get_db_connection
from kaloriekassen.google_health import replication


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 8, 16)


def test_replication_tracks_partial_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "replication.db"))
    monkeypatch.setattr(
        replication, "get_credentials", lambda: SimpleNamespace(token="token")
    )
    monkeypatch.setattr(replication, "date", FixedDate)
    received_filters = []

    def fetch(_token, *, filter_expression):
        received_filters.append(filter_expression)
        return [
            {
                "name": "exercise/1",
                "exercise": {
                    "interval": {
                        "startTime": "2026-08-14T22:30:00Z",
                        "startUtcOffset": "7200s",
                        "endTime": "2026-08-14T23:30:00Z",
                    },
                    "exerciseType": "RUNNING",
                    "metricsSummary": {
                        "caloriesKcal": 640,
                        "steps": "7200",
                        "distanceMillimeters": 10000000,
                    },
                },
                "dataSource": {
                    "application": {"packageName": "com.google.android.apps.fitness"}
                },
            },
            {"exercise": {"exerciseType": "RUNNING"}},
        ]

    monkeypatch.setattr(
        replication,
        "fetch_exercises",
        fetch,
    )

    assert replication.replicate(3) == 2
    assert received_filters == [
        'exercise.interval.civil_start_time >= "2026-08-14T00:00:00" '
        'AND exercise.interval.civil_start_time < "2026-08-17T00:00:00"'
    ]

    with get_db_connection() as connection:
        records = connection.execute(
            """SELECT google_health_id, activity_date, exercise_type,
                      calories_kcal, steps, distance_meters, source_package
               FROM raw_google_health_exercises"""
        ).fetchall()
        sync_run = connection.execute(
            """SELECT status, fetched_count, stored_count FROM sync_runs
               WHERE job = 'google-health-read'"""
        ).fetchone()

    assert records == [(
        "exercise/1", "2026-08-15", "RUNNING", 640.0, 7200, 10000.0,
        "com.google.android.apps.fitness",
    )]
    assert sync_run == ("partial", 2, 1)


def test_replication_normalizes_preexisting_payloads(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "legacy-payload.db"))
    monkeypatch.setattr(
        replication, "get_credentials", lambda: SimpleNamespace(token="token")
    )
    monkeypatch.setattr(replication, "date", FixedDate)
    monkeypatch.setattr(replication, "fetch_exercises", lambda *_args, **_kwargs: [])
    payload = {
        "exercise": {
            "interval": {"startTime": "2026-08-15T09:00:00+02:00"},
            "exerciseType": "GOLF",
            "metricsSummary": {"caloriesKcal": 700, "steps": "8500"},
        },
        "dataSource": {
            "application": {"packageName": "com.google.android.apps.fitness"}
        },
    }
    with get_db_connection() as connection:
        connection.execute(
            """INSERT INTO raw_google_health_exercises
               (google_health_id, start_time, exercise_type, payload)
               VALUES (?, ?, ?, ?)""",
            ("exercise/golf", "2026-08-15T09:00:00+02:00", "GOLF", json.dumps(payload)),
        )

    assert replication.replicate(3) == 0

    with get_db_connection() as connection:
        normalized = connection.execute(
            """SELECT activity_date, calories_kcal, steps, source_package
               FROM raw_google_health_exercises
               WHERE google_health_id = 'exercise/golf'"""
        ).fetchone()

    assert normalized == (
        "2026-08-15", 700.0, 8500, "com.google.android.apps.fitness"
    )
