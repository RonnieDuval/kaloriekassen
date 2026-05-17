# Kaloriekassen — Architecture

## Current Structure

```text
kaloriekassen/
├── src/                          # Main package
│   ├── __init__.py
│   ├── db.py                     # Database utilities
│   ├── logging_config.py         # Centralized logging setup
│   ├── sync_base.py              # Abstract base class for DB-backed syncs
│   └── syncs/                    # DB-backed sync implementations
│       ├── __init__.py
│       ├── fitbit.py             # FitbitSync class
│       └── intervals.py          # IntervalsSync class
├── MYFITNESSPAL/
│   └── hent_mfp_data.py          # Cookie-based MyFitnessPal nutrition fetch spike
├── sync_fitbit.py                # Fitbit entry point
├── sync_intervals.py             # Intervals.icu entry point
├── run_sync.py                   # CLI runner for DB-backed syncs
├── requirements.txt              # Dependencies
├── Dockerfile
├── docker-compose.yml
└── init.sql                      # Database schema, including raw_mfp for future MFP writes
```

## Key Principles

### 1. Shared DB sync infrastructure

Fitbit and Intervals.icu inherit from `BaseSyncAdapter` and use the common
fetch → upsert → log pattern.

### 2. MyFitnessPal is moving to cookie-based fetching

The old username/password based MyFitnessPal sync has been removed. The current
MyFitnessPal work lives in `MYFITNESSPAL/hent_mfp_data.py`, which uses the
`python-myfitnesspal` package's cookie handling by default. For Docker/non-browser
runs, optional `MFP_COOKIE_B` and `MFP_COOKIE_SESSION` values can be adapted into
the CookieJar shape accepted by `myfitnesspal.Client(cookiejar=...)`.

The next step is to validate the cookie-based fetch before wiring it back into
PostgreSQL writes.

### 3. Easy to Add New DB-backed Data Sources

```python
class StravaSync(BaseSyncAdapter):
    table_name = "raw_strava"
    columns = ["date", "calories_out", "distance_km"]

    def fetch_data(self) -> List[Dict]:
        # Only Strava-specific logic here
        pass
```

Then it automatically works with the common DB upsert flow.

## Usage

### Individual DB-backed entry points

```bash
python sync_fitbit.py
python sync_intervals.py
```

### CLI Runner

```bash
python run_sync.py              # Run DB-backed syncs
python run_sync.py fitbit       # Run Fitbit only
python run_sync.py intervals    # Run Intervals.icu only
```

### MyFitnessPal cookie fetch

```bash
python MYFITNESSPAL/hent_mfp_data.py
```

Optional Docker/non-browser cookie injection:

```env
MFP_COOKIE_B=...
MFP_COOKIE_SESSION=...
```

## File Responsibilities

| File | Purpose |
|------|---------|
| `src/db.py` | Database connection |
| `src/logging_config.py` | Centralized logging configuration |
| `src/sync_base.py` | Abstract base class with common DB sync logic |
| `src/syncs/fitbit.py` | FitbitSync implementation |
| `src/syncs/intervals.py` | Intervals.icu sync implementation |
| `MYFITNESSPAL/hent_mfp_data.py` | Cookie-based MyFitnessPal nutrition fetch |
| `sync_fitbit.py` / `sync_intervals.py` | Thin entry points for DB-backed syncs |
| `run_sync.py` | CLI orchestrator for DB-backed syncs |

## Future Improvements

1. **Wire MyFitnessPal into database writes**
   - Reuse the cookie-based payload once fetch stability is confirmed.
   - Write to the existing `raw_mfp` table.

2. **Connection Pooling** (`src/db.py`)
   - Add pgbouncer or psycopg2 connection pool.

3. **Retry Logic** (`src/sync_base.py`)
   - Exponential backoff for failed API calls.
   - Partial success handling.

4. **Scheduling** (`src/scheduler.py`)
   - APScheduler or Cron integration.
   - Replace `restart: "no"` with persistent services.

5. **Type Validation** (`src/validators.py`)
   - Pydantic models for data validation.
   - Catch invalid data before DB insert.

6. **Metrics & Monitoring** (`src/metrics.py`)
   - Track sync success/failure rates.
   - API response times.
   - Rows synced per source.
