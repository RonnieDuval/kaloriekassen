"""Intervals.icu to Google Health API sync adapter."""
import logging
from typing import Dict, List


from src.sync_base import BaseSyncAdapter
from GOOGLE_HEALTH_API.mappers import map_intervals_batch
from GOOGLE_HEALTH_API.uploader import upload_exercise_records, GoogleHealthUploadError
from GOOGLE_HEALTH_API.google_health_access import get_credentials

logger = logging.getLogger(__name__)


class IntervalsToGoogleHealthSync(BaseSyncAdapter):
    """
    Sync Intervals.icu workout data to Google Health API as exercise records.
    
    Flow:
    1. Read last N days from raw_intervals table
    2. Map to Google Health Exercise format
    3. Upload to Google Health API
    4. Log results
    
    Usage:
        # Upload last 7 days (default)
        sync = IntervalsToGoogleHealthSync()
        sync.run()
        
        # Upload last 150 days (backfill)
        sync = IntervalsToGoogleHealthSync(days_back=150)
        sync.run()
    
    Note: This sync only reads from DB and uploads to external API,
    so we don't use the standard table_name/columns upsert pattern.
    """

    table_name = "raw_intervals"
    columns = ["date"]  # Minimal columns - we read directly, not via upsert
    
    def __init__(self, days_back: int = 7):
        """
        Initialize sync adapter with Google Health API credentials.
        
        Args:
            days_back: Number of days to fetch and upload (default 7)
        """
        self.days_back = days_back
        
        # Ensure activities column exists for backwards compatibility
        from src.db import get_db_connection
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("ALTER TABLE raw_intervals ADD COLUMN IF NOT EXISTS activities JSONB;")
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not automatically add 'activities' column to 'raw_intervals' table: {e}")
            
        super().__init__()
        self.access_token = None
        self.refresh_token = None
        self._load_google_credentials()

    def _load_google_credentials(self):
        """Load Google OAuth credentials and refresh access token."""
        try:
            creds = get_credentials()
            self.access_token = creds.token
            self.refresh_token = creds.refresh_token
            logger.info("Loaded and refreshed Google Health API credentials")
        except Exception as e:
            raise RuntimeError(f"Failed to load Google credentials: {str(e)}")

    def fetch_data(self) -> List[Dict]:
        """
        Fetch last N days of Intervals.icu data from raw_intervals table.
        
        Returns:
            List of rows from raw_intervals (read-only, for mapping)
        """
        import datetime as dt
        from src.db import get_db_connection
        
        # Calculate start date in Python for database compatibility (Postgres/SQLite)
        start_date = dt.date.today() - dt.timedelta(days=self.days_back)
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT date, calories_out, distance_km, elevation_gain, workout_type, elapsed_time, activities
                    FROM raw_intervals
                    WHERE date >= %s
                    ORDER BY date DESC
                    """,
                    (start_date,)
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
                "elapsed_time": row[5],
                "activities": row[6],
            }
            for row in rows
        ]
        
        logger.info(f"Fetched {len(results)} days from raw_intervals (last {self.days_back} days)")
        return results

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
