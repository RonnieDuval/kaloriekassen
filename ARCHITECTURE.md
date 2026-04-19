# Kaloriekassen — Refactored Architecture

## New Structure

```
kaloriekassen/
├── src/                          # Main package
│   ├── __init__.py
│   ├── db.py                     # Database utilities (connection pooling)
│   ├── logging_config.py         # Centralized logging setup
│   ├── sync_base.py              # Abstract base class for all syncs
│   └── syncs/                    # Concrete sync implementations
│       ├── __init__.py
│       ├── fitbit.py             # FitbitSync class
│       ├── mfp.py                # MFPSync class
│       └── intervals.py          # IntervalsSync class
├── sync_fitbit.py                # Entry point (kept for docker-compose compatibility)
├── sync_mfp.py                   # Entry point
├── sync_intervals.py             # Entry point
├── run_sync.py                   # CLI runner for all/individual syncs
├── requirements.txt              # Dependencies
├── Dockerfile
├── docker-compose.yml
└── init.sql                      # Database schema
```

## Key Improvements

### 1. **Eliminated Code Duplication**
- **Before**: `get_db_conn()`, logging setup, and upsert logic repeated in all 3 files (~200 lines of duplication)
- **After**: Centralized in `BaseSyncAdapter` and utility modules

### 2. **Abstraction Layer**
- All syncs inherit from `BaseSyncAdapter`
- Only override `fetch_data()` method — sync-specific logic only
- Common pattern: fetch → upsert → log

### 3. **Easy to Add New Data Sources**
```python
class StravaSync(BaseSyncAdapter):
    table_name = "raw_strava"
    columns = ["date", "calories_out", "distance_km"]
    
    def fetch_data(self) -> List[Dict]:
        # Only Strava-specific logic here
        pass
```
Then it automatically works with the rest of the infrastructure.

### 4. **Better Error Handling**
- Centralized exception logging
- Clear error messages with context

### 5. **Better Logging**
- Consistent format across all syncs
- Easier to debug with structured logging

## Usage

### Individual Entry Points (for docker-compose)
```bash
python sync_fitbit.py
python sync_mfp.py
python sync_intervals.py
```

### CLI Runner
```bash
python run_sync.py              # Run all syncs
python run_sync.py fitbit       # Run Fitbit only
python run_sync.py mfp          # Run MyFitnessPal only
python run_sync.py intervals    # Run Intervals.icu only
```

## File Responsibilities

| File | Purpose |
|------|---------|
| `src/db.py` | Database connection (singleton-ready for future optimization) |
| `src/logging_config.py` | Centralized logging configuration |
| `src/sync_base.py` | Abstract base class with common sync logic |
| `src/syncs/fitbit.py` | FitbitSync implementation |
| `src/syncs/mfp.py` | MFPSync implementation |
| `src/syncs/intervals.py` | IntervalsSync implementation |
| `sync_*.py` | Thin entry points for docker-compose |
| `run_sync.py` | CLI orchestrator for running syncs |

## Future Improvements (Ready to Implement)

1. **Connection Pooling** (`src/db.py`)
   - Add pgbouncer or psycopg2 connection pool

2. **Retry Logic** (`src/sync_base.py`)
   - Exponential backoff for failed API calls
   - Partial success handling

3. **Scheduling** (`src/scheduler.py`)
   - APScheduler or Cron integration
   - Replace `restart: "no"` with persistent service

4. **Type Validation** (`src/validators.py`)
   - Pydantic models for data validation
   - Catch invalid data before DB insert

5. **Testing Framework** (`tests/`)
   - Mock APIs for unit tests
   - Integration tests with test database

6. **Metrics & Monitoring** (`src/metrics.py`)
   - Track sync success/failure rates
   - API response times
   - Rows synced per source

## Backward Compatibility

✅ **No breaking changes**: `docker-compose.yml` works as-is since root-level `sync_*.py` files are maintained as thin entry points.
