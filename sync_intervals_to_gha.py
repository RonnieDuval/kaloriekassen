#!/usr/bin/env python
"""Command-line entry point for Intervals.icu to Google Health API sync."""
import sys
import logging

from src.logging_config import setup_logging
from GOOGLE_HEALTH_API.sync_adapter import IntervalsToGoogleHealthSync

logger = logging.getLogger(__name__)


def main():
    """Run Intervals to Google Health sync."""
    setup_logging()
    
    try:
        logger.info("Starting Intervals to Google Health sync...")
        sync = IntervalsToGoogleHealthSync()
        exit_code = sync.run()
        
        if exit_code == 0:
            logger.info("Sync completed successfully")
        else:
            logger.error("Sync completed with errors")
        
        return exit_code
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
