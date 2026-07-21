# Kaloriekassen

Kaloriekassen er en lokal database for data fra Intervals.icu, MyFitnessPal og
Google Health. Hver integration har én vej og ét ansvar.

```text
Intervals.icu GET  → raw_intervals → Google Health POST
MyFitnessPal GET   → raw_mfp → nutrition_entries → analytical views
Google Health GET  → raw_google_health_exercises
```

`raw_mfp` stores one untouched diary payload per day. `nutrition_entries`
contains one row per food, while `nutrition_meal_totals` and
`daily_nutrition` provide meal and daily totals.

Google Health-replikaen er read-only: den bruges kun til lokal kontrol og
differenceanalyse og sendes aldrig til en anden tjeneste.

## Kommandoer

```bash
uv run kaloriekassen intervals google-health-export --days 7
uv run kaloriekassen myfitnesspal --days 7
uv run kaloriekassen google-health-export
uv run kaloriekassen google-health-read
uv run kaloriekassen google-health-auth
```

### MyFitnessPal

MyFitnessPal afviser login fra browserautomatisering. Log derfor ind manuelt i
din almindelige browser, find en godkendt diary-request i browserens DevTools,
og kopiér dens `Cookie`-header til `.env` som `MFP_COOKIE_HEADER=...`. Både
værdien alene og formen `Cookie: navn=værdi; ...` accepteres. Headeren er en
hemmelighed og må ikke commit'es.

En `Cookie`-header kan godt begynde med `euconsent-v2`; den cookie er kun et
samtykke. Headeren skal også indeholde den aktive login-cookie (den tidligere
klient ledte efter `user_session`). Kopiér altid headeren fra en **vellykket
diary-request**, ikke fra login-siden eller cookie-listen. Del aldrig selve
cookie-værdierne ved fejlsøgning — fejlbeskeden viser kun cookie-navne.
Derefter henter `uv run kaloriekassen myfitnesspal --days 7` diary-siderne med
den eksisterende session uden at forsøge et automatiseret login. Når sessionen
udløber, skal headeren kopieres igen efter manuelt login.

Det første svarer til den tidligere kommando `uv run run_sync.py intervals
google-health`: Intervals hentes først, og derefter eksporteres endnu ikke
eksporterede aktiviteter til Google Health. `google-health-read` er en separat,
read-only replika-kørsel.

### Google Health OAuth

OAuth bruger to separate filer, som begge skal blive under `secrets/` og aldrig
committes:

```text
secrets/google_api_client_secrets.json  # downloadet fra Google Cloud Console
secrets/google_oauth_token.json         # genereret refresh-token
```

Proceduren er:

1. Opret en OAuth-klient i Google Cloud Console. En Desktop-klient er enklest
   til lokal brug; en Web-klient virker også, hvis `http://localhost:8080/` er
   registreret som redirect-URI.
2. Download klientens JSON-fil og gem den som
   `secrets/google_api_client_secrets.json`.
3. Kør `uv run kaloriekassen google-health-auth` og godkend de ønskede scopes i
   browseren. Programmet gemmer refresh-tokenet i
   `secrets/google_oauth_token.json`.
4. Ved normale kørsler bruger programmet refresh-tokenet til automatisk at
   hente kortlivede access-tokens. Browserflowet skal kun gentages, hvis tokenet
   bliver ugyldigt, klienten ændres, eller der tilføjes scopes.

Stierne kan om nødvendigt ændres med `GOOGLE_CLIENT_SECRETS_PATH` og
`GOOGLE_TOKEN_STORE_PATH` i `.env`. Hvis Google afviser refresh-tokenet med
`invalid_grant`, starter programmet automatisk OAuth-flowet igen.

Hvis du tidligere har fået `Failed to spawn: kaloriekassen`, så opdatér til en
version med pakkekonfigurationen her og kør `uv sync` én gang. Derefter virker
`uv run kaloriekassen ...` også fra PowerShell.


## Databasevalg

Databasen vælges automatisk: på din computer bruges SQLite i
`kaloriekassen.db`; i en container bruges PostgreSQL. Sæt `DB_TYPE=sqlite` eller
`DB_TYPE=postgres` i `.env` for at overstyre. Docker Compose starter PostgreSQL
som `db` og sætter automatisk `DB_HOST=db` for sync-containeren.

`google-health-export` eksporterer kun Intervals-aktiviteter, der ikke allerede
har en succesfuld eksport i `google_health_exports`.
