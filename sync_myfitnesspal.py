#!/usr/bin/env python3
"""MyFitnessPal sync entry point.

Fetches the last 7 days of nutrition data from MyFitnessPal via browser automation
and upserts to the raw_mfp table in PostgreSQL.

Usage:
    python sync_myfitnesspal.py
"""
import logging
import sys

from src.syncs.myfitnesspal import MyFitnessPalSync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

if __name__ == "__main__":
    try:
        sync = MyFitnessPalSync()
        sync.run()
    except Exception as e:
        logging.error("Sync failed: %s", str(e), exc_info=True)
        sys.exit(1)
