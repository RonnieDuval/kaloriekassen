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
uv run kaloriekassen intervals --days 7
uv run kaloriekassen myfitnesspal --days 7
uv run kaloriekassen google-health-export
uv run kaloriekassen google-health-read
```

`google-health-export` eksporterer kun Intervals-aktiviteter, der ikke allerede
har en succesfuld eksport i `google_health_exports`.
