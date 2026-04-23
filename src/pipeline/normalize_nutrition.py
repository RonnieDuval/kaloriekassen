"""Normalize MFP meal entries into nutrition_entry."""
import datetime as dt
import logging

from src.db import get_db_connection

logger = logging.getLogger(__name__)


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def normalize_nutrition_entries(days_back: int = 7) -> int:
    oldest = dt.date.today() - dt.timedelta(days=max(days_back, 1) - 1)
    upserted = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_event_id, event_date, payload
                FROM raw_event
                WHERE source = 'mfp'
                  AND source_event_type = 'meal_entry'
                  AND event_date >= %s
                ORDER BY ingested_at ASC
                """,
                (oldest,),
            )
            entries = cur.fetchall()

            for raw_event_id, source_entry_id, entry_date, payload in entries:
                nutrition = payload.get("nutrition_information") if isinstance(payload, dict) else {}
                if not isinstance(nutrition, dict):
                    nutrition = {}

                cur.execute(
                    """
                    INSERT INTO nutrition_entry (
                        source,
                        source_entry_id,
                        consumed_ts,
                        entry_date,
                        meal_name,
                        food_name,
                        calories,
                        protein_g,
                        carbs_g,
                        fat_g,
                        raw_event_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source, source_entry_id) DO UPDATE SET
                        meal_name = EXCLUDED.meal_name,
                        food_name = EXCLUDED.food_name,
                        calories = EXCLUDED.calories,
                        protein_g = EXCLUDED.protein_g,
                        carbs_g = EXCLUDED.carbs_g,
                        fat_g = EXCLUDED.fat_g,
                        raw_event_id = EXCLUDED.raw_event_id,
                        updated_at = NOW()
                    """,
                    (
                        "mfp",
                        source_entry_id,
                        f"{entry_date.isoformat()}T12:00:00",
                        entry_date,
                        payload.get("meal_name") if isinstance(payload, dict) else None,
                        payload.get("food_name") if isinstance(payload, dict) else None,
                        int(_num(nutrition.get("calories"))),
                        _num(nutrition.get("protein")),
                        _num(nutrition.get("carbohydrates")),
                        _num(nutrition.get("fat")),
                        raw_event_id,
                    ),
                )
                upserted += 1

        conn.commit()

    logger.info("Normalized nutrition entries: %d upserted", upserted)
    return upserted
