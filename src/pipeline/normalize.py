"""Normalization pipeline from raw_event to canonical tables."""
import datetime as dt
import hashlib
import json
import logging
from typing import Any, Dict, Optional

from src.db import get_db_connection

logger = logging.getLogger(__name__)


def _make_dedupe_key(start_ts: Optional[str], activity_type: Optional[str], distance_m: int, calories: int) -> str:
    rounded_start = (start_ts or "")[:16]
    base = f"{rounded_start}|{activity_type or 'unknown'}|{round(distance_m / 100) * 100}|{round(calories / 25) * 25}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _parse_intervals_activity(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    payload = raw_event["payload"]
    start_ts = payload.get("start_date_local") or payload.get("start_date")
    distance_m = int(float(payload.get("distance") or 0))
    calories = int(payload.get("calories") or 0)
    return {
        "source": "intervals",
        "source_activity_id": str(payload.get("id") or raw_event["source_event_id"]),
        "raw_event_id": raw_event["id"],
        "start_ts": start_ts,
        "end_ts": payload.get("end_date_local") or payload.get("end_date"),
        "activity_type": payload.get("type") or "workout",
        "distance_m": distance_m,
        "calories_out": calories,
        "steps": int(payload.get("steps") or 0),
        "dedupe_key": _make_dedupe_key(start_ts, payload.get("type"), distance_m, calories),
    }


def _parse_fitbit_activity(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    payload = raw_event["payload"]
    start_ts = payload.get("startTime")
    if start_ts and "T" not in start_ts and raw_event.get("event_date"):
        start_ts = f"{raw_event['event_date']}T{start_ts}"

    distance_m = int(float(payload.get("distance") or 0) * 1000)
    calories = int(payload.get("calories") or 0)
    return {
        "source": "fitbit",
        "source_activity_id": str(payload.get("logId") or raw_event["source_event_id"]),
        "raw_event_id": raw_event["id"],
        "start_ts": start_ts,
        "end_ts": None,
        "activity_type": payload.get("activityName") or "workout",
        "distance_m": distance_m,
        "calories_out": calories,
        "steps": int(payload.get("steps") or 0),
        "dedupe_key": _make_dedupe_key(start_ts, payload.get("activityName"), distance_m, calories),
    }


def normalize_activities(days_back: int = 7) -> int:
    """Normalize raw activity events into canonical activity + activity_source_link."""
    oldest = dt.date.today() - dt.timedelta(days=max(days_back, 1) - 1)
    inserted = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source, source_event_id, event_date, payload
                FROM raw_event
                WHERE source_event_type = 'activity'
                  AND event_date >= %s
                ORDER BY ingested_at ASC
                """,
                (oldest,),
            )
            raw_events = [
                {
                    "id": row[0],
                    "source": row[1],
                    "source_event_id": row[2],
                    "event_date": row[3],
                    "payload": row[4] if isinstance(row[4], dict) else json.loads(row[4]),
                }
                for row in cur.fetchall()
            ]

            for raw_event in raw_events:
                if raw_event["source"] == "intervals":
                    parsed = _parse_intervals_activity(raw_event)
                elif raw_event["source"] == "fitbit":
                    parsed = _parse_fitbit_activity(raw_event)
                else:
                    continue

                cur.execute(
                    """
                    SELECT a.id
                    FROM activity a
                    JOIN activity_source_link l ON l.activity_id = a.id
                    WHERE l.source = %s AND l.source_activity_id = %s
                    """,
                    (parsed["source"], parsed["source_activity_id"]),
                )
                linked = cur.fetchone()
                if linked:
                    continue

                cur.execute("SELECT id FROM activity WHERE dedupe_key = %s", (parsed["dedupe_key"],))
                existing = cur.fetchone()
                if existing:
                    activity_id = existing[0]
                    confidence = 0.90
                else:
                    canonical_uid = f"act_{parsed['dedupe_key'][:16]}"
                    cur.execute(
                        """
                        INSERT INTO activity (
                            canonical_uid, start_ts, end_ts, activity_type,
                            calories_out, distance_m, steps, dedupe_key
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            canonical_uid,
                            parsed["start_ts"],
                            parsed["end_ts"],
                            parsed["activity_type"],
                            parsed["calories_out"],
                            parsed["distance_m"],
                            parsed["steps"],
                            parsed["dedupe_key"],
                        ),
                    )
                    activity_id = cur.fetchone()[0]
                    inserted += 1
                    confidence = 1.0

                cur.execute(
                    """
                    INSERT INTO activity_source_link (
                        activity_id, source, source_activity_id, raw_event_id, confidence
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source, source_activity_id) DO NOTHING
                    """,
                    (
                        activity_id,
                        parsed["source"],
                        parsed["source_activity_id"],
                        parsed["raw_event_id"],
                        confidence,
                    ),
                )

        conn.commit()

    logger.info("Normalized activities: %d inserted", inserted)
    return inserted
