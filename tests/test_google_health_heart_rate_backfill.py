import json

from kaloriekassen.google_health import heart_rate_backfill
from kaloriekassen.google_health.mapper import map_single_activity_to_google_exercise


def _activity():
    return {
        "id": "i123",
        "start_date": "2026-08-15T17:50:47Z",
        "timezone": "Europe/Copenhagen",
        "elapsed_time": 3516,
        "type": "Ride",
        "distance": 25793.21,
        "calories": 775,
        "average_heartrate": 170,
    }


def test_match_requires_google_web_source_name_and_distance():
    mapped = map_single_activity_to_google_exercise(_activity())
    record = {
        "dataSource": {
            "platform": "GOOGLE_WEB_API",
            "recordingMethod": "ACTIVELY_MEASURED",
        },
        "exercise": mapped["exercise"],
    }

    assert heart_rate_backfill._record_matches_activity(record, mapped)
    record["dataSource"]["platform"] = "FITBIT"
    assert not heart_rate_backfill._record_matches_activity(record, mapped)


def test_backfill_patches_unique_match_and_saves_google_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "backfill.db"))
    activity = _activity()
    mapped = map_single_activity_to_google_exercise(activity)
    google_id = "users/1/dataTypes/exercise/dataPoints/1234"

    from kaloriekassen.db import get_db_connection

    with get_db_connection() as connection:
        connection.execute(
            "INSERT INTO raw_intervals (activity_id, started_at, payload) VALUES (?, ?, ?)",
            ("i123", "2026-08-15T19:50:47", json.dumps(activity)),
        )
        connection.execute(
            """INSERT INTO google_health_exports
               (intervals_activity_id, request_payload, status)
               VALUES (?, ?, 'sent')""",
            ("i123", json.dumps(mapped)),
        )
        connection.execute(
            """INSERT INTO raw_google_health_exercises
               (google_health_id, start_time, payload)
               VALUES (?, ?, ?)""",
            (
                google_id,
                "2026-08-15T17:50:47Z",
                json.dumps(
                    {
                        "dataSource": {
                            "platform": "GOOGLE_WEB_API",
                            "recordingMethod": "ACTIVELY_MEASURED",
                        },
                        "exercise": mapped["exercise"],
                    }
                ),
            ),
        )

    calls = []
    monkeypatch.setattr(
        heart_rate_backfill,
        "get_credentials",
        lambda: type("Credentials", (), {"token": "access"})(),
    )
    monkeypatch.setattr(
        heart_rate_backfill,
        "patch_exercise_record",
        lambda token, name, payload: calls.append((token, name, payload)),
    )

    assert heart_rate_backfill.backfill_average_heart_rate(730) == 1
    assert calls[0][0:2] == ("access", google_id)
    assert calls[0][2]["exercise"]["metricsSummary"][
        "averageHeartRateBeatsPerMinute"
    ] == "170"

    with get_db_connection() as connection:
        row = connection.execute(
            "SELECT google_health_id, request_payload FROM google_health_exports"
        ).fetchone()
    assert row[0] == google_id
    assert json.loads(row[1])["exercise"]["metricsSummary"][
        "averageHeartRateBeatsPerMinute"
    ] == "170"
