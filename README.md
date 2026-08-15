# Kaloriekassen

Kaloriekassen er et privat, single-user værktøj til data fra Intervals.icu,
MyFitnessPal og Google Health. Det kan bruges lokalt med SQLite eller køre
permanent på en NAS med Docker Compose, scheduler og PostgreSQL. Hver
integration har én vej og ét ansvar.

```text
Intervals.icu GET  → raw_intervals → Google Health POST
MyFitnessPal GET   → raw_mfp → nutrition_entries → analytical views
Google Health GET  → raw_google_health_exercises
```

`raw_mfp` gemmer ét urørt dagbogspayload pr. dag. `nutrition_entries` indeholder
én række pr. fødevare, mens `nutrition_meal_totals` og `daily_nutrition` viser
totaler pr. måltid og dag.

Google Health-replikaen er read-only: den bruges kun til lokal kontrol og
differenceanalyse og sendes aldrig til en anden tjeneste.

## Kommandoer

```bash
uv run kaloriekassen intervals google-health-export --days 7
uv run kaloriekassen myfitnesspal --days 7
uv run kaloriekassen google-health-export
uv run kaloriekassen google-health-read
uv run kaloriekassen google-health-auth
uv run kaloriekassen status
uv run kaloriekassen scheduler
```

`status` viser den seneste kørsel for hvert sync-job, antal hentede og gemte
poster, seneste bekræftede datodækning samt fejlede dage. En tom, men korrekt
hentet dag registreres særskilt fra en dag, der ikke kunne hentes; manglende
kostdata bliver derfor ikke fortolket som nul kalorier.

## NAS og scheduler

Docker Compose kører Kaloriekassen som et privat, single-user værktøj med en
langtidkørende scheduler og PostgreSQL. Start det fra projektmappen på NAS'en:

```bash
docker compose up -d --build
docker compose logs -f scheduler
```

Scheduler-containeren venter på PostgreSQLs healthcheck, kører alle jobs én
gang ved opstart og gentager dem derefter uden overlap. Intervallerne styres i
`.env`:

```text
SCHEDULER_TIMEZONE=Europe/Copenhagen
SYNC_DAYS=7
INTERVALS_SYNC_MINUTES=30
MFP_SYNC_HOURS=3
GOOGLE_HEALTH_READ_HOURS=6
```

`secrets/` bind-mountes i containeren og skal indeholde både OAuth-klientfilen
og refresh-tokenet. Mappen skal blive privat og må ikke committes.

Scheduler-containeren kører med `GOOGLE_OAUTH_INTERACTIVE=false`. Hvis Google
afviser refresh-tokenet, registreres jobbet som fejlet i stedet for at forsøge
at åbne en browser på NAS'en. Kør da følgende på en computer med browser og
kopiér eller skriv tokenfilen til NAS'ens `secrets/`-mappe:

```bash
uv run kaloriekassen google-health-auth
```

Hvis OAuth-appens publishing status er `Testing`, udløber Google Health refresh
tokens efter syv dage. En privat app kan sættes til `In production` uden at
offentliggøre kildekode, NAS eller sundhedsdata; det fjerner testtilstandens
syv-dagesudløb. Se [Googles officielle vejledning](https://developers.google.com/health/setup).

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

Når `intervals` og `google-health-export` angives sammen, hentes Intervals-data
først, hvorefter endnu ikke eksporterede aktiviteter sendes til Google Health.
Scheduleren bevarer samme rækkefølge. `google-health-read` er en separat,
read-only replika-kørsel med pagination gennem alle tilgængelige sider.

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
`GOOGLE_TOKEN_STORE_PATH` i `.env`. Ved lokal, interaktiv kørsel starter
programmet automatisk OAuth-flowet igen, hvis Google afviser refresh-tokenet
med `invalid_grant`. Docker Compose sætter `GOOGLE_OAUTH_INTERACTIVE=false`, så
samme situation registreres som en fejl på NAS'en og skal løses fra en computer
med browser.

Hvis du tidligere har fået `Failed to spawn: kaloriekassen`, så opdatér til en
version med pakkekonfigurationen her og kør `uv sync` én gang. Derefter virker
`uv run kaloriekassen ...` også fra PowerShell.


## Databasevalg

Databasen vælges automatisk: på din computer bruges SQLite i
`kaloriekassen.db`; i en container bruges PostgreSQL. Sæt `DB_TYPE=sqlite` eller
`DB_TYPE=postgres` i `.env` for at overstyre. Docker Compose starter PostgreSQL
som `db` og sætter eksplicit `DB_TYPE=postgres` og `DB_HOST=db` for
scheduler-containeren.

`google-health-export` eksporterer kun Intervals-aktiviteter, der ikke allerede
har en succesfuld eksport i `google_health_exports`. Ved nye uploads gemmes det
returnerede Google Health-ID sammen med status og det præcise request-payload.
