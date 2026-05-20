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
│       ├── fitbit.py             # FitbitSync class (→ raw_fitbit)
│       └── intervals.py          # IntervalsSync class (→ raw_intervals)
├── GOOGLE_HEALTH_API/            # Google Health API integration
│   ├── setup_google_health.py    # OAuth setup & refresh token management
│   ├── google_health_access.py   # Credential helpers & API client
│   ├── mappers.py                # Convert Intervals→Google Health format
│   ├── uploader.py               # POST to Google Health API
│   ├── sync_adapter.py           # Orchestrate DB→mapping→upload pipeline
│   └── README.md                 # Integration guide
├── INTERVALS_ICU/                # Intervals.icu folder
│   └── __init__.py
├── MYFITNESSPAL/                 # MyFitnessPal data fetcher
│   └── mfp_chatgpt.py            # Playwright browser automation
├── sync_intervals_to_gha.py      # Upload Intervals to Google Health (entry point)
├── run_sync.py                   # CLI runner: intervals, myfitnesspal, fitbit, google-health
├── requirements.txt              # Dependencies
├── Dockerfile
├── docker-compose.yml
└── init.sql                      # Database schema (raw_mfp, raw_intervals, raw_fitbit)
```

## Key Principles

### 1. Shared DB sync infrastructure

Fitbit and Intervals.icu inherit from `BaseSyncAdapter` and use the common
fetch → upsert → log pattern. Each source writes to its own raw table:
- `raw_fitbit` (Fitbit data)
- `raw_intervals` (Intervals.icu data)
- `raw_mfp` (MyFitnessPal data)

### 2. MyFitnessPal uses Playwright browser automation

MyFitnessPal data is fetched via `MYFITNESSPAL/mfp_chatgpt.py` using Playwright
to automate browser login and data extraction. The script:
- Copies the local Chrome profile to avoid repeated logins
- Extracts nutrition data (meals, calories, macros) from the food diary
- Supports fetching single days, date ranges, or recent weeks
- Runs with `--visible` flag for manual login if needed

The next step is to wire the fetched data back into PostgreSQL (`raw_mfp` table)
and integrate it with the sync pipeline.

### 3. Google Health API integration (in progress)

`GOOGLE_HEALTH_API/` handles OAuth setup and credential management:
- `setup_google_health.py` — Interactive OAuth flow to obtain & store refresh token
- `google_health_access.py` — Credential helpers to refresh access tokens on demand

**Status:** Infrastructure is in place. The plan is to:
1. Decide on data flow direction (pull from Google Health vs. push to Google Health)
2. Build fetcher or writer module to handle actual data transfer
3. Integrate with the database sync pipeline

### 4. Easy to Add New DB-backed Data Sources

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

### Run all syncs (Fitbit + Intervals + MyFitnessPal + Google Health)

```bash
python run_sync.py
```

### Run individual syncs

```bash
python run_sync.py intervals          # Fetch Intervals → raw_intervals
python run_sync.py myfitnesspal       # Fetch MyFitnessPal → raw_mfp
python run_sync.py fitbit             # Fetch Fitbit → raw_fitbit
python run_sync.py google-health      # Upload Intervals → Google Health API
```

Or upload to Google Health directly:

```bash
python sync_intervals_to_gha.py       # Standalone upload script
```

### MyFitnessPal browser automation

Fetch data for a single day:

```bash
python MYFITNESSPAL/mfp_chatgpt.py 2026-05-13
```

Fetch a date range:

```bash
python MYFITNESSPAL/mfp_chatgpt.py --from 2026-05-01
```

Fetch the last 7 days:

```bash
python MYFITNESSPAL/mfp_chatgpt.py --last-week
```

Open browser for manual login:

```bash
python MYFITNESSPAL/mfp_chatgpt.py --visible 2026-05-13
```

### Google Health API workflow

**Setup (one-time):**

```bash
python GOOGLE_HEALTH_API/setup_google_health.py
```

This opens browser for Google login, requests `googlehealth.activity_and_fitness` scope, and saves refresh token to `secrets/google_oauth_token.json`.

**Upload Intervals workouts to Google Health:**

```bash
python run_sync.py google-health      # Via CLI
# or
python sync_intervals_to_gha.py       # Direct entry point
```

This:
1. Reads last 7 days from `raw_intervals` (Intervals.icu data)
2. Maps each workout to Google Health Exercise format
3. Validates access token (auto-refreshes if needed)
4. POSTs to Google Health API endpoint
5. Reports success/failure per record

**Verify upload in Google Health app:**
- Open Google Health app
- Go to "My data" → "Workouts"
- Should see exercise records synced from Intervals.icu

## File Responsibilities

| File | Purpose |
|------|---------|
| `src/db.py` | Database connection & utilities |
| `src/logging_config.py` | Centralized logging configuration |
| `src/sync_base.py` | Abstract base class with common DB sync logic |
| `src/syncs/fitbit.py` | FitbitSync implementation → `raw_fitbit` |
| `src/syncs/intervals.py` | IntervalsSync implementation → `raw_intervals` |
| `src/syncs/myfitnesspal.py` | MyFitnessPalSync implementation → `raw_mfp` |
| `GOOGLE_HEALTH_API/setup_google_health.py` | OAuth flow & token setup |
| `GOOGLE_HEALTH_API/google_health_access.py` | Credential management & token refresh |
| `GOOGLE_HEALTH_API/mappers.py` | Convert Intervals.icu → Google Health Exercise format |
| `GOOGLE_HEALTH_API/uploader.py` | POST exercise records to Google Health API |
| `GOOGLE_HEALTH_API/sync_adapter.py` | Orchestrate: read raw_intervals → map → authenticate → upload |
| `MYFITNESSPAL/mfp_chatgpt.py` | Playwright browser automation for MyFitnessPal |
| `run_sync.py` | CLI orchestrator: intervals, myfitnesspal, fitbit, google-health |
| `sync_intervals_to_gha.py` | Direct entry point for Google Health upload |

## Future Improvements

### High Priority

1. **Wire MyFitnessPal into database writes**
   - Complete Playwright payload integration
   - Write to `raw_mfp` table via sync pipeline
   - Validate data quality before insertion

2. **Google Health API integration**
   - Decide on data flow direction:
     - **Pull**: Fetch workouts/activities from Google Health into `raw_google_health` table
     - **Push**: Send synced nutrition/activity data back to Google Health
   - Build fetcher or writer module
   - Integrate with existing sync pipeline
   - Handle API rate limits & error states

### Medium Priority

3. **Connection Pooling** (`src/db.py`)
   - Add pgbouncer or psycopg2 connection pool
   - Reduce connection overhead for frequent syncs

4. **Retry Logic** (`src/sync_base.py`)
   - Exponential backoff for failed API calls
   - Partial success handling

5. **Scheduling** (`src/scheduler.py`)
   - APScheduler or Cron integration
   - Replace `restart: "no"` with persistent services

### Low Priority

6. **Type Validation** (`src/validators.py`)
   - Pydantic models for data validation
   - Catch invalid data before DB insert

7. **Metrics & Monitoring** (`src/metrics.py`)
   - Track sync success/failure rates
   - API response times
   - Rows synced per source
