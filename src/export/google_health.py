"""Minimal Google Health export scaffolding.

This module keeps export state in DB for idempotent sync.
"""
import hashlib
import json
import logging
from typing import Dict, Iterable

from src.db import get_db_connection

logger = logging.getLogger(__name__)


class GoogleHealthExporter:
    """Queue and mark exports without overdesigning the API integration."""

    def queue_activities(self, activities: Iterable[Dict]) -> int:
        queued = 0
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for activity in activities:
                    payload = {
                        "canonical_uid": activity.get("canonical_uid"),
                        "activity_type": activity.get("activity_type"),
                        "start_ts": str(activity.get("start_ts")),
                        "end_ts": str(activity.get("end_ts")),
                        "calories_out": activity.get("calories_out"),
                        "distance_m": activity.get("distance_m"),
                        "steps": activity.get("steps"),
                    }
                    export_hash = hashlib.sha256(
                        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
                    cur.execute(
                        """
                        INSERT INTO export_google_health_activity (activity_id, export_hash)
                        VALUES (%s, %s)
                        ON CONFLICT (activity_id, export_hash) DO NOTHING
                        """,
                        (activity["id"], export_hash),
                    )
                    if cur.rowcount:
                        queued += 1
            conn.commit()
        logger.info("Queued %d activities for Google Health export", queued)
        return queued

    def fetch_pending_activity_exports(self, limit: int = 100):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id, e.activity_id, a.canonical_uid, a.activity_type, a.start_ts, a.end_ts,
                           a.calories_out, a.distance_m, a.steps
                    FROM export_google_health_activity e
                    JOIN activity a ON a.id = e.activity_id
                    WHERE e.status = 'pending'
                    ORDER BY e.created_at ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return cur.fetchall()

    def mark_activity_export_result(self, export_id: int, success: bool, external_id: str | None = None, error: str | None = None) -> None:
        status = "exported" if success else "failed"
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE export_google_health_activity
                    SET status = %s,
                        external_id = COALESCE(%s, external_id),
                        error_message = %s,
                        attempts = attempts + 1,
                        last_attempted_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (status, external_id, error, export_id),
                )
            conn.commit()
