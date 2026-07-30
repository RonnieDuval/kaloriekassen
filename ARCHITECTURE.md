# Architecture

## Package layout

```text
src/kaloriekassen/
├── cli.py                   # command-line entry point
├── db.py                    # connections, schema and migrations
├── google_health/           # API client, auth, mapping and sync flows
├── intervals/               # API client and ingestion flow
└── myfitnesspal/            # diary client, transformation and ingestion
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
| `google_health_exports` | Intervals export audit | database → Google Health |

Raw tables retain full source payloads. Google Health reads and uploads are
separate flows; the read replica is never an upload source.

## Database backend

Local runs use SQLite and containers use PostgreSQL when `DB_TYPE` is blank.
Both backends create the same application tables, views, and migrations when a
connection opens.
