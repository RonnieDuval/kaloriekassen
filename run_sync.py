#!/usr/bin/env python
"""CLI runner for syncing all data sources or individual ones."""
import sys
from src.logging_config import setup_logging
from src.syncs.fitbit import FitbitSync
from src.syncs.mfp import MFPSync
from src.syncs.intervals import IntervalsSync

logger = setup_logging(__name__)

SYNCS = {
    "fitbit": FitbitSync,
    "mfp": MFPSync,
    "intervals": IntervalsSync,
}


def run_all():
    """Run all syncs sequentially."""
    logger.info("Running all syncs...")
    failed = []
    
    for name, sync_class in SYNCS.items():
        try:
            logger.info("→ Starting %s sync", name)
            sync = sync_class()
            sync.run()
            logger.info("✓ %s sync completed", name)
        except Exception as e:
            logger.error("✗ %s sync failed: %s", name, e)
            failed.append(name)
    
    if failed:
        logger.error("Failed syncs: %s", ", ".join(failed))
        return 1
    else:
        logger.info("✓ All syncs completed successfully")
        return 0


def run_single(name: str):
    """Run a single sync by name."""
    if name not in SYNCS:
        logger.error("Unknown sync: %s. Available: %s", name, ", ".join(SYNCS.keys()))
        return 1
    
    try:
        sync = SYNCS[name]()
        sync.run()
        return 0
    except Exception as e:
        logger.error("Sync failed: %s", e)
        return 1


def main():
    """CLI entry point."""
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == "all"):
        return run_all()
    elif len(sys.argv) == 2:
        return run_single(sys.argv[1])
    else:
        print("Usage: python run_sync.py [all|fitbit|mfp|intervals]")
        print("  all (default) - run all syncs")
        print("  fitbit        - run Fitbit sync only")
        print("  mfp           - run MyFitnessPal sync only")
        print("  intervals     - run Intervals.icu sync only")
        return 1


if __name__ == "__main__":
    sys.exit(main())
