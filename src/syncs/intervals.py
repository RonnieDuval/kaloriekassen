"""Intervals.icu data sync adapter."""
import logging
from typing import Dict, List

from src.sync_base import BaseSyncAdapter
from src.fetchers.intervals import IntervalsFetcher
from src.db import get_db_connection


logger = logging.getLogger(__name__)


class IntervalsSync(BaseSyncAdapter):
    """Sync Intervals.icu workout data aggregated by day.
    
    Fetches configurable number of days (default 7) from Intervals.icu API
    and syncs to raw_intervals table.
    
    Usage:
        # Fetch and sync last 7 days (default)
        sync = IntervalsSync()
        sync.run()
        
        # Fetch and sync last 150 days (backfill)
        sync = IntervalsSync(days_back=150)
        sync.run()
    """

    table_name = "raw_intervals"
    columns = ["date", "calories_out", "distance_km", "elevation_gain", "workout_type", "elapsed_time", "activities"]

    def __init__(self, days_back: int = 7):
        """
        Initialize sync adapter.
        
        Args:
            days_back: Number of days to fetch from Intervals.icu (default 7)
        """
        self.days_back = days_back
        self.fetcher = IntervalsFetcher(days_back=days_back)
        
        # Ensure activities column exists in the database
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("ALTER TABLE raw_intervals ADD COLUMN IF NOT EXISTS activities JSONB;")
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not automatically add 'activities' column to 'raw_intervals' table: {e}")
            
        super().__init__()

    def fetch_data(self) -> List[Dict]:
        """Fetch and aggregate Intervals.icu data for configured date range."""
        return self.fetcher.fetch_aggregated()
