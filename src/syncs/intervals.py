"""Intervals.icu data sync adapter."""
import logging
from typing import Dict, List

from src.sync_base import BaseSyncAdapter
from src.fetchers.intervals import IntervalsFetcher

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
    columns = ["date", "calories_out", "distance_km", "elevation_gain", "workout_type", "elapsed_time"]

    def __init__(self, days_back: int = 7):
        """
        Initialize sync adapter.
        
        Args:
            days_back: Number of days to fetch from Intervals.icu (default 7)
        """
        self.days_back = days_back
        self.fetcher = IntervalsFetcher(days_back=days_back)
        super().__init__()

    def fetch_data(self) -> List[Dict]:
        """Fetch and aggregate Intervals.icu data for configured date range."""
        return self.fetcher.fetch_aggregated()
