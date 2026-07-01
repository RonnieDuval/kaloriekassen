#!/usr/bin/env python3
"""CLI runner for database-backed syncs.

Orchestrates fetching and syncing data from multiple sources (Intervals.icu, MyFitnessPal, Fitbit)
into their respective PostgreSQL tables, and uploading to Google Health API.

Usage:
    python run_sync.py                                # Run all syncs (default 7 days)
    python run_sync.py intervals                      # Run Intervals.icu only (default 7 days)
    python run_sync.py myfitnesspal                   # Run MyFitnessPal only
    python run_sync.py fitbit                         # Run Fitbit only
    python run_sync.py google-health                  # Run Intervals → Google Health upload (default 7 days)
    python run_sync.py intervals myfitnesspal         # Multiple syncs
    
    # Backfill options (applies to intervals and google-health)
    python run_sync.py intervals --days 150           # Backfill 150 days
    python run_sync.py google-health --days 30        # Upload last 30 days to GHA
    python run_sync.py intervals google-health --days 60  # Sync and upload last 60 days
"""
import argparse
import inspect
import logging
import sys
from typing import List

from src.syncs.intervals import IntervalsSync
from src.syncs.myfitnesspal import MyFitnessPalSync
from src.syncs.fitbit import FitbitSync
from GOOGLE_HEALTH_API.sync_adapter import IntervalsToGoogleHealthSync
from google.auth.exceptions import RefreshError
from google.auth.exceptions import RefreshError
from GOOGLE_HEALTH_API.setup_google_health import main as run_oauth_flow

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
        "google-health": IntervalsToGoogleHealthSync,
    }


def run_syncs(sync_names: List[str], days_back: int = 7, visible: bool = False) -> int:
    """Run specified syncs.
    
    Args:
        sync_names: List of sync names to run, or empty list for all syncs.
        days_back: Number of days to fetch (applies to Intervals and Google Health syncs)
        visible: Run browser automation in visible/headed mode (if supported)
    
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
            logger.info("Starting %s sync (days_back=%d)...", sync_name, days_back)
            sync_class = available[sync_name]
            
            def create_sync_instance():
                sig = inspect.signature(sync_class)
                if "visible" in sig.parameters:
                    return sync_class(days_back=days_back, visible=visible)
                return sync_class(days_back=days_back)

            try:
                # 1. Første forsøg på at starte sync-klassen
                sync = create_sync_instance()
            except RefreshError:
                # Denne blok rammes KUN, hvis det er Google, og tokenet er dødt
                logger.warning("Google token expired for %s. Starting OAuth flow...", sync_name)
                
                # Kør dit browser-setup
                run_oauth_flow()
                
                logger.info("OAuth flow completed. Retrying %s sync...", sync_name)
                # 2. Andet forsøg med det nye friske token
                sync = create_sync_instance()
            
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
        help="Which syncs to run (intervals, myfitnesspal, fitbit, google-health). If none specified, runs all.",
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to fetch (applies to intervals and google-health syncs). Default: 7",
    )
    
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Run browser automation in visible/headed mode (useful for initial login on Windows)",
    )
    
    args = parser.parse_args()
    
    exit_code = run_syncs(args.syncs, days_back=args.days, visible=args.visible)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
