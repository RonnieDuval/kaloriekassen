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
                        "startTime": "2026-08-15T10:00:00+02:00",
                        "endTime": "2026-08-15T11:00:00+02:00",
                    },
                    "exerciseType": "BIKING",
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
            "SELECT google_health_id, exercise_type FROM raw_google_health_exercises"
        ).fetchall()
        sync_run = connection.execute(
            """SELECT status, fetched_count, stored_count FROM sync_runs
               WHERE job = 'google-health-read'"""
        ).fetchone()

    assert records == [("exercise/1", "BIKING")]
    assert sync_run == ("partial", 2, 1)
