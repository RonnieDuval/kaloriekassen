"""Intervals.icu to Google Health API sync adapter."""
import datetime as dt
import logging
import os
from typing import Dict, List, Any

import psycopg2.extras

from src.sync_base import BaseSyncAdapter
from GOOGLE_HEALTH_API.mappers import map_intervals_batch
from GOOGLE_HEALTH_API.uploader import upload_exercise_records, GoogleHealthUploadError
from GOOGLE_HEALTH_API.google_health_access import get_fresh_access_token

logger = logging.getLogger(__name__)


class IntervalsToGoogleHealthSync(BaseSyncAdapter):
    """
    Sync Intervals.icu workout data to Google Health API as exercise records.
    
    Flow:
    1. Read last 7 days from raw_intervals table
    2. Map to Google Health Exercise format
    3. Upload to Google Health API
    4. Log results
    """

    table_name = "raw_intervals"
    
    def __init__(self):
        """Initialize sync adapter with Google Health API credentials."""
        super().__init__()
        self.access_token = None
        self.refresh_token = None
        self._load_google_credentials()

    def _load_google_credentials(self):
        """Load Google OAuth credentials from file."""
        google_token_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "secrets",
            "google_oauth_token.json"
        )
        
        if not os.path.exists(google_token_file):
            raise FileNotFoundError(
                f"Google OAuth token file not found: {google_token_file}. "
                "Run setup_google_health.py first."
            )
        
        try:
            self.access_token, self.refresh_token = get_fresh_access_token(
                google_token_file
            )
            logger.info("Loaded Google Health API credentials")
        except Exception as e:
            raise RuntimeError(f"Failed to load Google credentials: {str(e)}")

    def fetch_data(self) -> List[Dict]:
        """
        Fetch last 7 days of Intervals.icu data from raw_intervals table.
        
        Returns:
            List of rows from raw_intervals (read-only, for mapping)
        """
        # Note: We don't use self.columns here since we read from DB
        # This is a read-only fetch for upload purposes
        
        cursor = self.get_db_cursor()
        try:
            cursor.execute(
                """
                SELECT date, calories_out, distance_km, elevation_gain, workout_type
                FROM raw_intervals
                WHERE date >= (CURRENT_DATE - INTERVAL '6 days')
                ORDER BY date DESC
                """
            )
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            results = [
                {
                    "date": row[0],
                    "calories_out": row[1],
                    "distance_km": row[2],
                    "elevation_gain": row[3],
                    "workout_type": row[4],
                }
                for row in rows
            ]
            
            logger.info(f"Fetched {len(results)} days from raw_intervals")
            return results
            
        finally:
            cursor.close()

    def run(self) -> int:
        """
        Execute full sync pipeline: fetch → map → upload.
        
        Returns:
            0 on success, 1 on failure
        """
        logger.info("Starting Intervals → Google Health sync...")
        
        try:
            # Fetch data from database
            logger.info(f"Fetching data from {self.table_name}...")
            intervals_data = self.fetch_data()
            
            if not intervals_data:
                logger.warning("No data fetched from raw_intervals")
                return 0
            
            # Map to Google Health format
            logger.info(f"Mapping {len(intervals_data)} records to Google Health format...")
            google_health_data = map_intervals_batch(intervals_data)
            
            if not google_health_data:
                logger.warning("No valid exercise records to upload (all rows may lack workout_type)")
                return 0
            
            logger.info(f"Mapped {len(google_health_data)} exercise records")
            
            # Upload to Google Health API
            logger.info(f"Uploading {len(google_health_data)} records to Google Health API...")
            upload_results = upload_exercise_records(
                access_token=self.access_token,
                exercise_data_points=google_health_data
            )
            
            # Log results
            successful = len(upload_results["successful"])
            failed = len(upload_results["failed"])
            total = upload_results["total"]
            
            logger.info(
                f"Upload complete: {successful}/{total} successful, {failed} failed"
            )
            
            if failed > 0:
                logger.warning("Failed uploads:")
                for failure in upload_results["failed"]:
                    logger.warning(
                        f"  {failure['date']}: {failure.get('error', 'unknown error')}"
                    )
            
            return 0 if failed == 0 else 1
            
        except GoogleHealthUploadError as e:
            logger.error(f"Google Health API error: {str(e)}")
            return 1
        except Exception as e:
            logger.error(f"Sync failed: {str(e)}", exc_info=True)
            return 1
        finally:
            self.close_db()


def main():
    """Entry point for Intervals → Google Health sync."""
    sync = IntervalsToGoogleHealthSync()
    exit_code = sync.run()
    return exit_code


if __name__ == "__main__":
    import sys
    from src.logging_config import setup_logging
    
    setup_logging()
    sys.exit(main())
