# Architecture

## Package layout

```text
src/kaloriekassen/
├── cli.py                   # command-line entry point
├── db.py                    # connections, schema and migrations
├── scheduler.py             # long-running, sequential NAS scheduler
├── sync_tracking.py         # run history, date coverage and status reporting
├── google_health/           # API client, auth, mapping and sync flows
├── intervals/               # API client and ingestion flow
├── myfitnesspal/            # diary client, transformation and ingestion
└── withings/                # OAuth, API client, transformation and ingestion
```

Code is grouped by external system. A domain owns its client, transformation,
and synchronization flow instead of spreading those responsibilities across
technical layers.

## Data ownership

| Table or view | Owner | Direction |
|---|---|---|
| `raw_intervals` | Intervals.icu activities | API → database |
| `raw_mfp` | MyFitnessPal diary days | API → database |
| `nutrition_entries` | Normalized MyFitnessPal foods | derived locally |
| `nutrition_meal_totals` | Meal-level nutrition totals | derived view |
| `daily_nutrition` | Daily nutrition totals | derived view |
| `raw_google_health_exercises` | Google Health exercise replica | API → database, read-only |
| `google_health_daily_activity` | Daily steps, active energy and TDEE | API → database, read-only |
| `google_health_exports` | Intervals export audit | database → Google Health |
| `user_profile` | Height and calculation settings | configured locally |
| `body_measurements` | Weight and body composition | Withings → database |
| `daily_energy_summary` | Daily intake, expenditure and estimated balance | derived view |
| `sync_runs` | Operational history for every sync job | derived locally |
| `sync_coverage` | Per-source date coverage and missing-data state | derived locally |

Raw tables retain full source payloads. Google Health reads and uploads are
separate flows; the read replica is never an upload source.

Every operational sync creates a `sync_runs` row with `running`, `success`,
`partial`, or `failed` status. Intervals and MyFitnessPal also update
`sync_coverage` for every requested date. Coverage distinguishes verified days
with data, verified empty days, and failed days.

## NAS scheduling

Docker Compose runs PostgreSQL and one long-lived scheduler container. The
scheduler executes jobs sequentially, immediately at startup and then at
environment-configured intervals. Intervals ingestion and Google Health export
form one ordered job; MyFitnessPal ingestion and the Google Health read replica
have independent intervals. A failed job is recorded and does not stop later
jobs.

Interactive OAuth is disabled in the scheduler container. Refresh-token
rejection becomes a tracked failure and must be repaired from a computer with
a browser. The host `secrets/` directory is mounted into the container so a
replacement token is visible without rebuilding the image.

Explicit OAuth commands can upload their client and token JSON files through
the computer's existing OpenSSH client on port 22. Uploads use a temporary file
and remote rename; the local token is deleted only after success. OAuth browser
callbacks remain local to the computer, and Docker exposes no OAuth ports.

The deployment deliberately uses interval scheduling instead of a public
webhook endpoint. This keeps the private NAS closed to inbound integration
traffic. Database upserts, export auditing and date coverage make repeated
polling idempotent and observable.

## Daily energy model

`daily_energy_summary` treats Google Health `total-calories` as the preferred
TDEE estimate. Its step and Intervals exercise fields are explanatory
components and are never added to that total. This prevents double counting
when Google has already reconciled activity from several sources.
Basal energy is calculated independently with Mifflin–St Jeor from the profile
and the latest available body weight; it is not inferred by subtracting two
Google rollups.

## Database backend

Local runs use SQLite by default. Containers auto-detect PostgreSQL when
`DB_TYPE` is blank, while Docker Compose sets `DB_TYPE=postgres` explicitly.
Both backends create the same application tables, views, and migrations when a
connection opens.
