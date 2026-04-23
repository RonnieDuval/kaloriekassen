"""Base class for all data sync adapters."""
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List

from psycopg2.extras import Json, execute_values

from src.db import get_db_connection

logger = logging.getLogger(__name__)


class BaseSyncAdapter(ABC):
    """Abstract base class for syncing data from external sources to database."""

    # Subclasses must override these
    table_name: str = None
    columns: List[str] = None
    days_back: int = 7

    def __init__(self):
        if not self.table_name:
            raise ValueError(f"{self.__class__.__name__}.table_name not set")
        if not self.columns:
            raise ValueError(f"{self.__class__.__name__}.columns not set")

    @abstractmethod
    def fetch_data(self) -> List[Dict]:
        """Fetch data from external source for the last N days.

        Returns:
            List of dicts with keys matching self.columns, plus 'date' as first key.
        """
        pass

    def fetch_raw_events(self) -> List[Dict]:
        """Optional hook for immutable source payloads."""
        return []

    def after_sync(self) -> None:
        """Optional hook for normalization steps after ingest."""

    def upsert_to_db(self, rows: List[Dict]) -> None:
        """Upsert rows to database table.

        Args:
            rows: List of dicts with column values
        """
        if not rows:
            logger.info("No rows to upsert for %s", self.table_name)
            return

        col_names = ["date"] + [c for c in self.columns if c != "date"]
        set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in self.columns if col != "date"])
        set_clause += ", updated_at = NOW()"

        sql = f"""
            INSERT INTO {self.table_name} ({', '.join(col_names)})
            VALUES %s
            ON CONFLICT (date) DO UPDATE SET
                {set_clause};
        """

        values = [tuple(r.get(col) for col in col_names) for r in rows]

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, values)
            conn.commit()

        logger.info("Upserted %d rows to %s", len(rows), self.table_name)

    def insert_raw_events(self, events: List[Dict]) -> None:
        """Store immutable source payloads in raw_event."""
        if not events:
            return

        sql = """
            INSERT INTO raw_event (
                source,
                source_event_type,
                source_event_id,
                event_ts,
                event_date,
                payload_sha256,
                payload
            )
            VALUES %s
            ON CONFLICT (source, source_event_type, payload_sha256) DO NOTHING
        """

        values = []
        for event in events:
            payload = event.get("payload") or {}
            payload_raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            payload_sha256 = hashlib.sha256(payload_raw.encode("utf-8")).hexdigest()
            values.append(
                (
                    event["source"],
                    event["source_event_type"],
                    str(event.get("source_event_id") or ""),
                    event.get("event_ts"),
                    event.get("event_date"),
                    payload_sha256,
                    Json(payload),
                )
            )

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, values)
            conn.commit()

        logger.info("Inserted %d raw events for %s", len(values), self.table_name)

    def run(self) -> None:
        """Main sync orchestration: fetch and upsert."""
        try:
            logger.info("Starting sync for %s", self.table_name)
            rows = self.fetch_data()
            self.upsert_to_db(rows)
            self.insert_raw_events(self.fetch_raw_events())
            self.after_sync()
            logger.info("Successfully completed sync for %s", self.table_name)
        except Exception:
            logger.exception("Sync failed for %s", self.table_name)
            raise
