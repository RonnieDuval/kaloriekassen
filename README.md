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

## Kørsel med interval i container

Hvis `run_sync.py` skal køre løbende i en container, kan du bruge `sync_scheduler` servicen i `docker-compose.yml`.

Servicen har **indbyggede defaults** i `docker-compose.yml`:

- `SYNC_TARGETS`: `intervals myfitnesspal fitbit google-health`
- `SYNC_DAYS`: `7`
- `SYNC_INTERVAL_SECONDS`: `21600` (6 timer)

Det betyder, at den kan starte uden at du sætter dem i `.env`.

Hvis du vil override defaults, kan du sætte dem i `.env` (valgfrit):

```env
SYNC_TARGETS=intervals myfitnesspal
SYNC_DAYS=14
SYNC_INTERVAL_SECONDS=3600
```

Start scheduleren:

```bash
docker compose up --build sync_scheduler
```


Sæt credentials i `docker-compose.yml` eller via miljøvariabler.

## MyFitnessPal - Browser automation via Playwright

MyFitnessPal-data hentes via Playwright-baseret browser automation. Scriptet kopier din lokale Chrome-profil og bruger den til at logge ind automatisk.

### Setup

Sørg for at Chrome er installeret lokalt. Skriptet finder den automatisk fra `~/.config/google-chrome`.

### Brug

Hent data for en enkelt dag:

```bash
python MYFITNESSPAL/mfp_chatgpt.py 2026-05-13
```

Hent data for en periode:

```bash
python MYFITNESSPAL/mfp_chatgpt.py --from 2026-05-01
```

Hent data for de seneste 7 dage:

```bash
python MYFITNESSPAL/mfp_chatgpt.py --last-week
```

Hvis du skal logge ind manuelt, kør med `--visible`:

```bash
python MYFITNESSPAL/mfp_chatgpt.py --visible 2026-05-13
```

Browseren åbnes, og du kan logge ind manuelt. Derefter henter scriptet data. Din session gemmes i `temp_chrome_profile/`, så senere kald er automatiske.

## Google Health OAuth setup

Google Health setup er et **interaktivt engangs-flow**. Scriptet åbner Google-login i browseren, du godkender adgangen, og derefter kopierer du `code`-parameteren fra redirect URL'en tilbage i terminalen.

Vi beholder den simple proces, fordi den virker og er nem at fejlsøge. OAuth-consent i browseren kan ikke fjernes helt, fordi Google kræver brugerens login og godkendelse, før der udstedes en authorization code.

### 1. Opret lokal `.env`

Kopiér eksempel-filen og udfyld dine egne værdier:

```bash
cp .env.example .env
```

`.env` skal som minimum indeholde:

```env
GOOGLE_CLIENT_ID=din_client_id
GOOGLE_CLIENT_SECRET=din_client_secret
GOOGLE_REDIRECT_URI=https://www.google.com
# Valgfri: default er secrets/google_oauth_token.json
GOOGLE_TOKEN_STORE_PATH=secrets/google_oauth_token.json
```

`GOOGLE_REDIRECT_URI` skal matche en autoriseret redirect URI på OAuth-clienten i Google Cloud Console.

### 2. Hent refresh token første gang

Kør:

```bash
python GOOGLE_HEALTH_API/setup_google_health.py
```

Scriptet gør følgende uden at ændre på OAuth-logikken:

1. bygger Google authorization URL ud fra `.env`
2. åbner URL'en i browseren
3. du logger ind og godkender adgangen hos Google
4. Google redirecter til `GOOGLE_REDIRECT_URI` med en URL, der indeholder `code=...`
5. du kopierer kun værdien fra `code`-parameteren og indsætter den i terminalen
6. scriptet bytter auth code til tokens og gemmer refresh token lokalt

Eksempel på redirect URL:

```text
https://www.google.com/?code=4/0Ab...xyz&scope=https://www.googleapis.com/auth/googlehealth.activity_and_fitness
```

I eksemplet skal du kopiere værdien mellem `code=` og `&scope`.

### 3. Daglig brug efter setup

Når refresh token findes i token-filen, kan koden hente credentials uden nyt browser-login:

```python
from GOOGLE_HEALTH_API.google_health_access import get_credentials

creds = get_credentials()
```

`get_credentials()` læser refresh token fra `GOOGLE_TOKEN_STORE_PATH` og refresher access token automatisk, når `refresh_now=True` (default).

### Hvis refresh token ikke virker længere

Kør setup-scriptet igen og hent en ny auth code, hvis refresh token ikke længere kan bruges. Typiske årsager er:

- token-filen under `secrets/` er slettet
- brugeren har fjernet appens adgang i Google Account settings
- refresh token har ikke været brugt i længere tid
- OAuth consent screen står som **External / Testing**
- Google svarer med `invalid_grant` under refresh

### Sikkerhed

- Del aldrig `GOOGLE_CLIENT_SECRET` eller refresh token.
- Commit aldrig `.env` eller indholdet af `secrets/`.
- Token-filen oprettes med begrænsede filrettigheder (`0600`) hvor operativsystemet understøtter det.
