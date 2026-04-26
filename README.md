# KalorieKassen

KalorieKassen synkroniserer data fra flere kilder til PostgreSQL med én råtabel per kilde.

## Kilder
- **MyFitnessPal** -> `raw_mfp`
- **Intervals.icu** -> `raw_intervals`
- **Fitbit** -> `raw_fitbit`

`daily_balance` prioriterer `calories_out` fra Intervals.icu. Hvis der ikke findes data for dagen, bruges Fitbit.

## Kørsel
```bash
docker compose up --build
```

Sæt credentials i `docker-compose.yml` eller via miljøvariabler.
