#!/usr/bin/env python3
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
import settings

SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.writeonly"
]

def main():
    print("🔐 Google Health OAuth Setup (Official SDK)")
    print("=" * 50)
    
    # 1. Indlæser din eksisterende client_secret JSON-fil
    flow = InstalledAppFlow.from_client_secrets_file(
        'google_api_client_secrets2.json', 
        scopes=SCOPES
    )
    breakpoint()
    # 2. Starter en midlertidig, lokal baggrundsserver på port 8080.
    # Den åbner browseren automatisk, fanger tokens i luften og lukker sig selv med det samme.
    credentials = flow.run_local_server(
        port=8080, 
        prompt="consent",
        access_type="offline"
    )

    # 3. Gemmer tokens præcis i det format og den sti, dit system kender
    token_store_path = Path(settings.GOOGLE_TOKEN_STORE_PATH)
    token_store_path.parent.mkdir(parents=True, exist_ok=True)

    token_data = {
        "refresh_token": credentials.refresh_token,
        # "token": credentials.token,
        # "client_id": credentials.client_id,
        # "client_secret": credentials.client_secret,
    }

    token_store_path.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
    
    try:
        token_store_path.chmod(0o600)
    except (OSError, NotImplementedError):
        pass

    print("\n✅ Success! Token er gemt, og du kan nu køre din container helt automatisk.")

if __name__ == "__main__":
    main()