# Kaloriekassen

Kaloriekassen er et privat, single-user værktøj til data fra Intervals.icu,
MyFitnessPal og Google Health. Det kan bruges lokalt med SQLite eller køre
permanent på en NAS med Docker Compose, scheduler og PostgreSQL. Hver
integration har én vej og ét ansvar.

```text
Intervals.icu GET  → raw_intervals → Google Health POST
MyFitnessPal GET   → raw_mfp → nutrition_entries → analytical views
Google Health GET  → raw_google_health_exercises
Google Health rollup → google_health_daily_activity → daily_energy_summary
Withings GET       → body_measurements → daily_energy_summary
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
uv run kaloriekassen google-health-read --days 3
uv run kaloriekassen google-health-daily --days 90
uv run kaloriekassen google-health-heart-rate-backfill --days 730
uv run kaloriekassen google-health-auth
uv run kaloriekassen withings --days 30
uv run kaloriekassen withings-auth
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

NAS'ens secrets-mappe bind-mountes som `/app/secrets` i containeren og skal
indeholde både OAuth-klientfiler og tokens. Den fysiske sti sættes med
`SECRETS_DIR` i NAS'ens `.env`. Mappen skal blive privat og må ikke committes.

Scheduler-containeren kører med `GOOGLE_OAUTH_INTERACTIVE=false`. Hvis Google
afviser refresh-tokenet, registreres jobbet som fejlet i stedet for at forsøge
at åbne en browser på NAS'en. OAuth køres på en computer med browser:

```bash
uv run kaloriekassen google-health-auth
```

Sæt `OAUTH_UPLOAD_TO_NAS=true`, `NAS_SSH_HOST`, `NAS_SSH_USER` og
`NAS_SECRETS_DIR` i computerens lokale `.env`. Kommandoen uploader derefter
både klient- og tokenfil atomisk gennem computerens eksisterende OpenSSH/SCP
på port 22. Den lokale tokenfil slettes først, når upload og remote rename er
lykkedes; ved fejl bevares den til recovery. SSH bruger normal nøgle og
`known_hosts`, så password skal ikke ligge i `.env`. Der åbnes ingen OAuth-porte
i Docker eller på NAS'en.

Hvis OAuth-appens publishing status er `Testing`, udløber Google Health refresh
tokens efter syv dage. En privat app kan sættes til `In production` uden at
offentliggøre kildekode, NAS eller sundhedsdata; det fjerner testtilstandens
syv-dagesudløb. Se [Googles officielle vejledning](https://developers.google.com/health/setup).

`google-health-daily` henter afsluttede kalenderdage med skridt, aktiv energi og
Google Healths samlede kalorieforbrug. API-kaldene deles automatisk i perioder,
der overholder Googles 14-dages grænse for energidata.

## Daglig energimodel

`daily_energy_summary` erstatter det tidligere misvisende `daily_balance`.
Google Healths `total-calories` bruges som estimeret TDEE, fordi værdien allerede
indeholder både basal- og aktivitetsforbrug. Træningskalorier fra Intervals og
estimerede skridtkalorier vises som forklarende datapunkter, men lægges ikke oven
i TDEE og bliver derfor ikke dobbeltregnet.

Basalforbruget beregnes stabilt med Mifflin–St Jeor ud fra den seneste vægt og
den lokale profil. Standardprofilen er 114 kg, 185 cm, mand og født 2. september
1986. Det giver 2.106,25 kcal/dag frem til næste fødselsdag. Når Withings senere
leverer en nyere vægt, overtager den automatisk standardvægten fra måledatoen.

Viewet viser blandt andet kalorieindtag, afledt basalforbrug, skridt,
træningskalorier, aktiv energi, TDEE, estimeret energibalance og
datakomplethed. Skridtkalorier bruger samme højde og vægtgrundlag som BMR.

`body_measurements` er den kanoniske destination for Withings-målinger. Den
normaliserer vægt, fedtprocent, fedtmasse og fedtfri masse fra `getmeas`.

### Withings OAuth og synkronisering

Withings kræver en offentlig HTTPS redirect-URL. Den lille Cloudflare Worker i
`cloudflare/withings-oauth-relay` opfylder kravet og videresender kun det
kortlivede OAuth-svar til `http://localhost:8081/`. Den gemmer ingen data og
indeholder ingen credentials. NAS'en er ikke offentligt tilgængelig og henter
senere selv data direkte fra Withings.

Proceduren er:

1. Opret Worker'en i Cloudflare med koden fra
   `cloudflare/withings-oauth-relay/src/index.js` og deploy den.
2. Registrer dens præcise URL hos Withings, inklusive `/oauth/callback`, fx
   `https://kaloriekassen-withings-oauth.<konto>.workers.dev/oauth/callback`.
3. Opret `secrets/withings_api_client.json` med de værdier, Withings viser:

   ```json
   {
     "client_id": "...",
     "client_secret": "...",
     "redirect_uri": "https://kaloriekassen-withings-oauth.<konto>.workers.dev/oauth/callback"
   }
   ```

4. Kør `uv run kaloriekassen withings-auth` på den computer, hvor browseren
   åbnes. Med NAS-upload aktiveret i `.env` sendes klient- og tokenfilen gennem
   SSH port 22 direkte til NAS'ens secrets-mappe, hvorefter den lokale tokenfil
   fjernes. NAS'en bliver dermed eneste ejer af det roterende refresh-token.
5. Test med `uv run kaloriekassen withings --days 730`. Derefter er en daglig
   kørsel med fx `--days 7` tilstrækkelig. Access-token fornyes automatisk, og
   det nye refresh-token erstatter altid det gamle.

Stierne kan ændres med `WITHINGS_CLIENT_SECRETS_PATH` og
`WITHINGS_TOKEN_STORE_PATH`.

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
Scheduleren bevarer samme rækkefølge.
Nye træninger får Intervals-feltet `average_heartrate` med som
`averageHeartRateBeatsPerMinute` i Google Health. Den eksplicitte
`google-health-heart-rate-backfill`-kommando opdaterer allerede eksporterede
træninger via deres eksisterende Google-ID og opretter derfor ikke dubletter.
`google-health-read` er en separat, read-only replika-kørsel. `--days` filtrerer
Google Health allerede ved API-kaldet, så en almindelig 3-dages sync ikke
genhenter hele træningshistorikken. Pagination gennemløber kun siderne inden
for den valgte periode.

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
   browseren. Uden NAS-upload gemmes refresh-tokenet lokalt. Med
   `OAUTH_UPLOAD_TO_NAS=true` uploades klient- og tokenfil gennem SSH, og den
   lokale tokenfil fjernes efter bekræftet upload.
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
