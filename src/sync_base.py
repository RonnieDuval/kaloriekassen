"""Base class for all data sync adapters."""
import datetime as dt
import logging
from abc import ABC, abstractmethod
from typing import Dict, List

from psycopg2.extras import execute_values

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

    def upsert_to_db(self, rows: List[Dict]) -> None:
        """Upsert rows to database table.
        
        Args:
            rows: List of dicts with column values
        """
        if not rows:
            logger.info("No rows to upsert for %s", self.table_name)
            return

        # Build column list (date first, then others)
        col_names = ["date"] + [c for c in self.columns if c != "date"]
        placeholders = ",".join(["%s"] * len(col_names))

        # Build SET clause for ON CONFLICT
        set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in self.columns if col != "date"])
        set_clause += ", updated_at = NOW()"

        sql = f"""
            INSERT INTO {self.table_name} ({', '.join(col_names)})
            VALUES %s
            ON CONFLICT (date) DO UPDATE SET
                {set_clause};
        """

        values = [
            tuple(r.get(col) for col in col_names)
            for r in rows
        ]

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, values)
            conn.commit()

        logger.info("Upserted %d rows to %s", len(rows), self.table_name)

    def run(self) -> None:
        """Main sync orchestration: fetch and upsert."""
        try:
            logger.info("Starting sync for %s", self.table_name)
            rows = self.fetch_data()
            self.upsert_to_db(rows)
            logger.info("Successfully completed sync for %s", self.table_name)
        except Exception as e:
            logger.exception("Sync failed for %s", self.table_name)
            raise
