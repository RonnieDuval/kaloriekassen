"""Export unsent Intervals activities to Google Health."""
from datetime import datetime, timezone
import json
from kaloriekassen.database.connection import execute, get_db_connection, json_value
from kaloriekassen.integrations.google_health.auth import get_credentials
from kaloriekassen.integrations.google_health.client import upload_exercise_records
from kaloriekassen.integrations.google_health.mapper import map_single_activity_to_google_exercise


def export() -> int:
    with get_db_connection() as conn:
        rows = execute(conn, """SELECT i.activity_id, i.payload FROM raw_intervals i
            LEFT JOIN google_health_exports e ON e.intervals_activity_id = i.activity_id AND e.status = 'sent'
            WHERE e.intervals_activity_id IS NULL ORDER BY i.started_at""").fetchall()
        if not rows:
            return 0
        access_token = get_credentials().token
        for activity_id, payload in rows:
            request_payload = map_single_activity_to_google_exercise(json.loads(payload))
            result = upload_exercise_records(access_token, [request_payload])
            status = "sent" if result["successful"] else "failed"
            error = result["failed"][0]["error"] if result["failed"] else None
            execute(conn, """INSERT INTO google_health_exports
                (intervals_activity_id, request_payload, status, last_error, attempted_at, sent_at)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(intervals_activity_id) DO UPDATE SET
                request_payload=excluded.request_payload, status=excluded.status, last_error=excluded.last_error,
                attempted_at=excluded.attempted_at, sent_at=excluded.sent_at""",
                (activity_id, json_value(request_payload), status, error, datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat() if status == "sent" else None))
    return len(rows)
