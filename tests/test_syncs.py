"""Tests for individual sync adapters."""
import datetime as dt
from unittest.mock import Mock, patch

from src.syncs.fitbit import FitbitSync
from src.syncs.mfp import MFPSync
from src.syncs.intervals import IntervalsSync


def test_fitbit_sync_config():
    """Test FitbitSync has correct configuration."""
    sync = FitbitSync()
    assert sync.table_name == "raw_fitbit"
    assert "calories_out" in sync.columns
    assert "steps" in sync.columns
    assert "distance_km" in sync.columns


def test_mfp_sync_config():
    """Test MFPSync has correct configuration."""
    sync = MFPSync()
    assert sync.table_name == "raw_mfp"
    assert "calories_in" in sync.columns
    assert "protein" in sync.columns
    assert "carbs" in sync.columns
    assert "fat" in sync.columns


def test_intervals_sync_config():
    """Test IntervalsSync has correct configuration."""
    sync = IntervalsSync()
    assert sync.table_name == "raw_intervals"
    assert "calories_out" in sync.columns
    assert "distance_km" in sync.columns
    assert "elevation_gain" in sync.columns
    assert "workout_type" in sync.columns


@patch.dict('os.environ', {'FITBIT_ACCESS_TOKEN': '', 'FITBIT_USER_ID': 'test'})
def test_fitbit_missing_token():
    """Test FitbitSync raises error when token missing."""
    sync = FitbitSync()
    try:
        sync.fetch_data()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "FITBIT_ACCESS_TOKEN" in str(e)


@patch.dict('os.environ', {'MFP_USERNAME': '', 'MFP_PASSWORD': 'test'})
def test_mfp_missing_credentials():
    """Test MFPSync raises error when credentials missing."""
    sync = MFPSync()
    try:
        sync.fetch_data()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "MFP_USERNAME or MFP_PASSWORD" in str(e)


@patch.dict('os.environ', {'INTERVALS_API_KEY': '', 'INTERVALS_ATHLETE_ID': 'test'})
def test_intervals_missing_key():
    """Test IntervalsSync raises error when API key missing."""
    sync = IntervalsSync()
    try:
        sync.fetch_data()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "INTERVALS_API_KEY or INTERVALS_ATHLETE_ID" in str(e)


if __name__ == "__main__":
    import sys
    
    tests = [
        test_fitbit_sync_config,
        test_mfp_sync_config,
        test_intervals_sync_config,
        test_fitbit_missing_token,
        test_mfp_missing_credentials,
        test_intervals_missing_key,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
    
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
