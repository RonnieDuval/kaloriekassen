# Architecture

## Package layout

```text
src/kaloriekassen/
├── cli.py
├── database/              # connections and local schema
├── integrations/          # API-specific clients and mapping
│   ├── intervals/
│   ├── myfitnesspal/
│   └── google_health/
└── services/              # explicit data flows
```

## Data ownership

| Table | Owner | Direction |
|---|---|---|
| `raw_intervals` | Intervals.icu activities | API → database |
| `raw_mfp` | MyFitnessPal diary days | API → database |
| `raw_google_health_exercises` | Google Health exercise replica | API → database, read-only |
| `google_health_exports` | Intervals export audit | database → Google Health |

`raw_intervals` is one record per activity, not one record per date. The full
source payload is retained. Google Health reads and uploads are deliberately
separate services; the read replica is never an upload source.

Fitbit is not part of the application.

## Database backend

When `DB_TYPE` is blank, local runs use SQLite and container runs use PostgreSQL.
Both backends create the same four application tables when a connection opens.
