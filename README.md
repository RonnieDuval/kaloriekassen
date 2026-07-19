# Kaloriekassen

Kaloriekassen er en lokal database for data fra Intervals.icu, MyFitnessPal og
Google Health. Hver integration har én vej og ét ansvar.

```text
Intervals.icu GET  → raw_intervals → Google Health POST
MyFitnessPal GET   → raw_mfp
Google Health GET  → raw_google_health_exercises
```

Google Health-replikaen er read-only: den bruges kun til lokal kontrol og
differenceanalyse og sendes aldrig til en anden tjeneste.

## Kommandoer

```bash
uv run kaloriekassen intervals google-health-export --days 7
uv run kaloriekassen myfitnesspal --days 7
uv run kaloriekassen google-health-export
uv run kaloriekassen google-health-read
```

Det første svarer til den tidligere kommando `uv run run_sync.py intervals
google-health`: Intervals hentes først, og derefter eksporteres endnu ikke
eksporterede aktiviteter til Google Health. `google-health-read` er en separat,
read-only replika-kørsel.

## Databasevalg

Databasen vælges automatisk: på din computer bruges SQLite i
`kaloriekassen.db`; i en container bruges PostgreSQL. Sæt `DB_TYPE=sqlite` eller
`DB_TYPE=postgres` i `.env` for at overstyre. Docker Compose starter PostgreSQL
som `db` og sætter automatisk `DB_HOST=db` for sync-containeren.

`google-health-export` eksporterer kun Intervals-aktiviteter, der ikke allerede
har en succesfuld eksport i `google_health_exports`.
