"""Live integration tests against the Intervals.icu API."""

import json
import os

import pytest
from dotenv import load_dotenv

from kaloriekassen.intervals.client import IntervalsFetcher


@pytest.mark.integration
def test_fetch_recent_activities_from_intervals_api():
    """Authenticate, fetch and print real activities from Intervals.icu."""
    load_dotenv()

    api_key = os.getenv("INTERVALS_API_KEY", "").strip()
    athlete_id = os.getenv("INTERVALS_ATHLETE_ID", "").strip()
    if not api_key or not athlete_id:
        pytest.skip("INTERVALS_API_KEY and INTERVALS_ATHLETE_ID are required")

    days_back = int(os.getenv("INTERVALS_TEST_DAYS", "3"))
    fetcher = IntervalsFetcher(days_back=days_back)

    # Verify that the live client received the real configuration before it
    # authenticates against Intervals.icu. Never print the API key.
    assert fetcher.api_key == api_key
    assert fetcher.athlete_id == athlete_id

    activities = fetcher.fetch_raw()

    print(
        json.dumps(
            {
                "days_back": days_back,
                "activity_count": len(activities),
                "activities": activities,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    assert isinstance(activities, list)
    assert activities, f"No activities returned for the last {days_back} days"
    assert all(isinstance(activity, dict) for activity in activities)
    assert all("id" in activity and "start_date_local" in activity for activity in activities)
