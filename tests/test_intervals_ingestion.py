import json

from kaloriekassen.db import get_db_connection
from kaloriekassen.intervals import sync as intervals_sync


def test_ingestion_stores_each_activity(monkeypatch, tmp_path):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("INTERVALS_API_KEY", "test-key")
    monkeypatch.setenv("INTERVALS_ATHLETE_ID", "test-athlete")
    monkeypatch.setattr(intervals_sync.IntervalsFetcher, "fetch_raw", lambda _: [
        {"id": "a", "start_date_local": "2026-01-01T10:00:00", "type": "Run", "calories": 42,
         "distance": 1000, "total_elevation_gain": 10, "elapsed_time": 300}
    ])
    assert intervals_sync.ingest(1) == 1
    with get_db_connection() as conn:
        row = conn.execute("SELECT activity_id, payload FROM raw_intervals").fetchone()
    assert row[0] == "a"
    assert json.loads(row[1])["type"] == "Run"
