#!/usr/bin/env python3
"""CLI runner for database-backed syncs.

Orchestrates fetching and syncing data from multiple sources (Intervals.icu, MyFitnessPal, Fitbit)
into their respective PostgreSQL tables.

Usage:
    python run_sync.py                # Run all syncs
    python run_sync.py intervals      # Run Intervals.icu only
    python run_sync.py myfitnesspal   # Run MyFitnessPal only
    python run_sync.py fitbit         # Run Fitbit only
"""
import argparse
import logging
import sys
from typing import List

from src.syncs.intervals import IntervalsSync
from src.syncs.myfitnesspal import MyFitnessPalSync
from src.syncs.fitbit import FitbitSync
from src.sync_base import BaseSyncAdapter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def get_available_syncs() -> dict:
    """Return mapping of sync names to sync classes."""
    return {
        "intervals": IntervalsSync,
        "myfitnesspal": MyFitnessPalSync,
        "fitbit": FitbitSync,
    }


def run_syncs(sync_names: List[str]) -> int:
    """Run specified syncs.
    
    Args:
        sync_names: List of sync names to run, or empty list for all syncs.
    
    Returns:
        0 on success, 1 on failure.
    """
    available = get_available_syncs()
    
    # If no syncs specified, run all
    if not sync_names:
        sync_names = list(available.keys())
        logger.info("Running all syncs: %s", ", ".join(sync_names))
    
    failed = []
    
    for sync_name in sync_names:
        if sync_name not in available:
            logger.error("Unknown sync: %s", sync_name)
            logger.info("Available syncs: %s", ", ".join(available.keys()))
            failed.append(sync_name)
            continue
        
        try:
            logger.info("Starting %s sync...", sync_name)
            sync_class = available[sync_name]
            sync = sync_class()
            sync.run()
            logger.info("%s sync completed successfully", sync_name)
        except Exception as e:
            logger.error("%s sync failed: %s", sync_name, str(e), exc_info=True)
            failed.append(sync_name)
    
    if failed:
        logger.error("Failed syncs: %s", ", ".join(failed))
        return 1
    
    logger.info("All syncs completed successfully")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run database-backed data syncs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "syncs",
        nargs="*",
        help="Which syncs to run (intervals, myfitnesspal, fitbit). If none specified, runs all.",
    )
    
    args = parser.parse_args()
    
    exit_code = run_syncs(args.syncs)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
