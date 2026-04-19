"""Unit tests for sync adapters."""
import datetime as dt
from unittest.mock import Mock, patch, MagicMock

from src.sync_base import BaseSyncAdapter


class MockSync(BaseSyncAdapter):
    """Mock sync adapter for testing."""
    
    table_name = "test_table"
    columns = ["date", "value1", "value2"]
    
    def fetch_data(self):
        today = dt.date.today()
        return [
            {"date": today, "value1": 10, "value2": 20},
            {"date": today - dt.timedelta(days=1), "value1": 15, "value2": 25},
        ]


def test_base_adapter_initialization():
    """Test that BaseSyncAdapter requires table_name and columns."""
    sync = MockSync()
    assert sync.table_name == "test_table"
    assert sync.columns == ["date", "value1", "value2"]
    assert sync.days_back == 7


def test_base_adapter_requires_table_name():
    """Test that BaseSyncAdapter raises error without table_name."""
    class BadSync(BaseSyncAdapter):
        columns = ["date"]
        def fetch_data(self):
            return []
    
    try:
        BadSync()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "table_name not set" in str(e)


def test_base_adapter_requires_columns():
    """Test that BaseSyncAdapter raises error without columns."""
    class BadSync(BaseSyncAdapter):
        table_name = "test"
        def fetch_data(self):
            return []
    
    try:
        BadSync()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "columns not set" in str(e)


def test_fetch_data():
    """Test that fetch_data returns expected format."""
    sync = MockSync()
    data = sync.fetch_data()
    
    assert len(data) == 2
    assert "date" in data[0]
    assert "value1" in data[0]
    assert "value2" in data[0]


@patch('src.sync_base.get_db_connection')
def test_upsert_empty_rows(mock_get_conn):
    """Test that upsert with empty rows logs and returns."""
    sync = MockSync()
    sync.upsert_to_db([])
    
    # Should not call DB connection for empty rows
    mock_get_conn.assert_not_called()


@patch('src.sync_base.get_db_connection')
def test_upsert_rows(mock_get_conn):
    """Test that upsert calls database with correct SQL."""
    # Setup mock connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    
    sync = MockSync()
    rows = [
        {"date": dt.date(2026, 4, 19), "value1": 10, "value2": 20},
    ]
    
    sync.upsert_to_db(rows)
    
    # Verify DB methods were called
    assert mock_get_conn.called
    assert mock_conn.commit.called


@patch('src.sync_base.logger')
@patch('src.sync_base.get_db_connection')
def test_run_success(mock_get_conn, mock_logger):
    """Test that run() orchestrates fetch + upsert successfully."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_get_conn.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    
    sync = MockSync()
    sync.run()
    
    # Verify logging
    assert mock_logger.info.call_count >= 2  # At least "Starting" and completion logs


@patch('src.sync_base.get_db_connection')
def test_run_failure(mock_get_conn):
    """Test that run() handles exceptions properly."""
    mock_get_conn.side_effect = Exception("DB connection failed")
    
    class FailingSync(BaseSyncAdapter):
        table_name = "test"
        columns = ["date"]
        def fetch_data(self):
            raise Exception("API error")
    
    sync = FailingSync()
    try:
        sync.run()
        assert False, "Should have raised exception"
    except Exception as e:
        assert "API error" in str(e)


if __name__ == "__main__":
    # Simple test runner
    import sys
    
    tests = [
        test_base_adapter_initialization,
        test_base_adapter_requires_table_name,
        test_base_adapter_requires_columns,
        test_fetch_data,
        test_upsert_empty_rows,
        test_upsert_rows,
        test_run_success,
        test_run_failure,
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
