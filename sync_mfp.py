import datetime as dt
import logging
import os
from typing import Dict, List

import myfitnesspal
import psycopg2
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


def fetch_mfp_last_7_days() -> List[Dict]:
    username = os.getenv("MFP_USERNAME", "")
    password = os.getenv("MFP_PASSWORD", "")

    if not username or not password:
        raise ValueError("Missing MFP credentials. Set MFP_USERNAME and MFP_PASSWORD.")

    client = myfitnesspal.Client(username, password)
    today = dt.date.today()
    rows: List[Dict] = []

    for offset in range(7):
        day = today - dt.timedelta(days=offset)
        diary = client.get_date(day.year, day.month, day.day)

        totals = diary.totals
        rows.append(
            {
                "date": day,
                "calories_in": int(totals.get("calories", 0) or 0),
                "protein": int(totals.get("protein", 0) or 0),
                "carbs": int(totals.get("carbohydrates", 0) or 0),
                "fat": int(totals.get("fat", 0) or 0),
            }
        )

    return rows


def upsert_mfp(rows: List[Dict]) -> None:
    if not rows:
        logger.info("No MFP rows to upsert")
        return

    sql = """
        INSERT INTO raw_mfp (date, calories_in, protein, carbs, fat)
        VALUES %s
        ON CONFLICT (date) DO UPDATE SET
            calories_in = EXCLUDED.calories_in,
            protein = EXCLUDED.protein,
            carbs = EXCLUDED.carbs,
            fat = EXCLUDED.fat,
            updated_at = NOW();
    """

    values = [
        (r["date"], r["calories_in"], r["protein"], r["carbs"], r["fat"])
        for r in rows
    ]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
        conn.commit()

    logger.info("Upserted %s MFP rows", len(rows))


def main() -> None:
    try:
        rows = fetch_mfp_last_7_days()
        upsert_mfp(rows)
    except Exception:
        logger.exception("sync_mfp failed")
        raise


if __name__ == "__main__":
    main()
