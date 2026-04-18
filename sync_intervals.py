import datetime as dt
import logging
import os
from typing import Dict, List

import psycopg2
import requests
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_db_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "kaloriekassen"),
        user=os.getenv("DB_USER", "kalorie"),
        password=os.getenv("DB_PASSWORD", "kalorie"),
    )


def fetch_intervals_last_7_days() -> List[Dict]:
    api_key = os.getenv("INTERVALS_API_KEY", "")
    athlete_id = os.getenv("INTERVALS_ATHLETE_ID", "")

    if not api_key or not athlete_id:
        raise ValueError(
            "Missing Intervals.icu credentials. Set INTERVALS_API_KEY and INTERVALS_ATHLETE_ID."
        )

    today = dt.date.today()
    oldest = today - dt.timedelta(days=6)

    url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/activities"
    params = {
        "oldest": oldest.isoformat(),
        "newest": today.isoformat(),
    }

    resp = requests.get(url, params=params, auth=("API_KEY", api_key), timeout=30)
    resp.raise_for_status()
    activities = resp.json()

    per_day: Dict[dt.date, Dict] = {}
    for item in activities:
        day = dt.date.fromisoformat(item.get("start_date_local", "")[:10])
        metrics = per_day.setdefault(
            day,
            {
                "date": day,
                "calories_out": 0,
                "distance_km": 0.0,
                "elevation_gain": 0,
                "workout_type": None,
            },
        )

        metrics["calories_out"] += int(item.get("calories", 0) or 0)
        metrics["distance_km"] += float(item.get("distance", 0) or 0) / 1000
        metrics["elevation_gain"] += int(item.get("total_elevation_gain", 0) or 0)
        workout_type = item.get("type")
        if workout_type:
            metrics["workout_type"] = workout_type

    rows: List[Dict] = []
    for offset in range(7):
        day = today - dt.timedelta(days=offset)
        rows.append(
            per_day.get(
                day,
                {
                    "date": day,
                    "calories_out": 0,
                    "distance_km": 0.0,
                    "elevation_gain": 0,
                    "workout_type": None,
                },
            )
        )

    return rows


def upsert_intervals(rows: List[Dict]) -> None:
    if not rows:
        logger.info("No Intervals rows to upsert")
        return

    sql = """
        INSERT INTO raw_intervals (date, calories_out, distance_km, elevation_gain, workout_type)
        VALUES %s
        ON CONFLICT (date) DO UPDATE SET
            calories_out = EXCLUDED.calories_out,
            distance_km = EXCLUDED.distance_km,
            elevation_gain = EXCLUDED.elevation_gain,
            workout_type = EXCLUDED.workout_type,
            updated_at = NOW();
    """

    values = [
        (
            r["date"],
            r["calories_out"],
            r["distance_km"],
            r["elevation_gain"],
            r["workout_type"],
        )
        for r in rows
    ]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
        conn.commit()

    logger.info("Upserted %s Intervals rows", len(rows))


def main() -> None:
    try:
        rows = fetch_intervals_last_7_days()
        upsert_intervals(rows)
    except Exception:
        logger.exception("sync_intervals failed")
        raise


if __name__ == "__main__":
    main()
