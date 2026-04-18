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


def fetch_fitbit_last_7_days() -> List[Dict]:
    access_token = os.getenv("FITBIT_ACCESS_TOKEN", "")
    user_id = os.getenv("FITBIT_USER_ID", "-")

    if not access_token:
        raise ValueError("Missing Fitbit token. Set FITBIT_ACCESS_TOKEN.")

    headers = {"Authorization": f"Bearer {access_token}"}
    today = dt.date.today()
    oldest = today - dt.timedelta(days=6)

    base = f"https://api.fitbit.com/1/user/{user_id}"
    calories_url = f"{base}/activities/calories/date/{oldest.isoformat()}/{today.isoformat()}.json"
    steps_url = f"{base}/activities/steps/date/{oldest.isoformat()}/{today.isoformat()}.json"
    distance_url = (
        f"{base}/activities/distance/date/{oldest.isoformat()}/{today.isoformat()}.json"
    )

    calories_resp = requests.get(calories_url, headers=headers, timeout=30)
    calories_resp.raise_for_status()
    steps_resp = requests.get(steps_url, headers=headers, timeout=30)
    steps_resp.raise_for_status()
    distance_resp = requests.get(distance_url, headers=headers, timeout=30)
    distance_resp.raise_for_status()

    calories_series = {
        dt.date.fromisoformat(item["dateTime"]): int(float(item.get("value") or 0))
        for item in calories_resp.json().get("activities-calories", [])
    }
    steps_series = {
        dt.date.fromisoformat(item["dateTime"]): int(float(item.get("value") or 0))
        for item in steps_resp.json().get("activities-steps", [])
    }
    distance_series = {
        dt.date.fromisoformat(item["dateTime"]): float(item.get("value") or 0)
        for item in distance_resp.json().get("activities-distance", [])
    }

    rows: List[Dict] = []
    for offset in range(7):
        day = today - dt.timedelta(days=offset)
        rows.append(
            {
                "date": day,
                "calories_out": calories_series.get(day, 0),
                "steps": steps_series.get(day, 0),
                "distance_km": distance_series.get(day, 0.0),
            }
        )

    return rows


def upsert_fitbit(rows: List[Dict]) -> None:
    if not rows:
        logger.info("No Fitbit rows to upsert")
        return

    sql = """
        INSERT INTO raw_fitbit (date, calories_out, distance_km, steps)
        VALUES %s
        ON CONFLICT (date) DO UPDATE SET
            calories_out = EXCLUDED.calories_out,
            distance_km = EXCLUDED.distance_km,
            steps = EXCLUDED.steps,
            updated_at = NOW();
    """

    values = [
        (r["date"], r["calories_out"], r["distance_km"], r["steps"])
        for r in rows
    ]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
        conn.commit()

    logger.info("Upserted %s Fitbit rows", len(rows))


def main() -> None:
    try:
        rows = fetch_fitbit_last_7_days()
        upsert_fitbit(rows)
    except Exception:
        logger.exception("sync_fitbit failed")
        raise


if __name__ == "__main__":
    main()
