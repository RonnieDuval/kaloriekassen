from types import SimpleNamespace

from kaloriekassen.db import get_db_connection
from kaloriekassen.google_health import replication


def test_replication_tracks_partial_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "replication.db"))
    monkeypatch.setattr(
        replication, "get_credentials", lambda: SimpleNamespace(token="token")
    )
    monkeypatch.setattr(
        replication,
        "fetch_exercises",
        lambda _token: [
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
        ],
    )

    assert replication.replicate() == 2

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
