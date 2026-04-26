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


## Google Health token storage (Level 1)
- Keep `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in environment variables.
- Refresh token is stored locally in `secrets/google_oauth_token.json` by default.
- Override location with `GOOGLE_TOKEN_STORE_PATH` when needed.
- Ensure `secrets/` is in `.gitignore` and file permissions are restricted.
