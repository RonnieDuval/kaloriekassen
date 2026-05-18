"""Sync adapters for different data sources."""
from src.syncs.fitbit import FitbitSync
from src.syncs.intervals import IntervalsSync

__all__ = ["FitbitSync", "IntervalsSync"]
