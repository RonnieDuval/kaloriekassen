# KalorieKassen

KalorieKassen synkroniserer data fra flere kilder til PostgreSQL med én råtabel per kilde.

## Kilder
- **MyFitnessPal** → `raw_mfp`
- **Intervals.icu** → `raw_intervals`
- **Fitbit** → `raw_fitbit`

`daily_balance` prioriterer `calories_out` fra Intervals.icu. Hvis der ikke findes data for dagen, bruges Fitbit.

## Health Connect
Health Connect har ikke en direkte server-side API på samme måde som Intervals/Fitbit.
Typisk kræver det en Android-app (eller eksport), som derefter kan synkroniseres videre.
Hvis du vil, kan næste step være et `sync_health_connect_import.py`, som indlæser en CSV/JSON-eksport.

## Kørsel
```bash
docker compose up --build
```

Sæt credentials i `docker-compose.yml` eller via miljøvariabler.
