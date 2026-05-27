#!/usr/bin/env python3
"""
Google Health OAuth setup script.

Steps:
1. Opens the Google OAuth URL in browser (user logs in and grants permission).
2. User pastes the auth_code from the redirect URL.
3. Script exchanges auth_code for refresh_token.
4. Saves refresh_token to secrets/google_oauth_token.json.
"""
import json
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import requests

import settings


# GOOGLE_HEALTH_SCOPE = "https://www.googleapis.com/auth/googlehealth.activity_and_fitness"
GOOGLE_HEALTH_SCOPE = "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.writeonly"


def get_auth_code() -> str:
    """Open browser and prompt user for auth_code from redirect URL."""
    auth_params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "access_type": "offline",
        "scope": GOOGLE_HEALTH_SCOPE,
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"

    print("\n🔐 Google Health OAuth Setup")
    print("=" * 50)
    print("\n1. Opening browser to Google login...\n")
    webbrowser.open(auth_url)

    print("2. After logging in and granting permission, you'll be redirected.")
    print("3. Copy the 'code' parameter from the redirect URL.\n")
    auth_code = input("Paste auth_code here: ").strip()

    if not auth_code:
        raise ValueError("Auth code cannot be empty")

    return auth_code


def exchange_auth_code_for_tokens(auth_code: str) -> dict:
    """Exchange auth_code for access_token and refresh_token."""
    print("\n⏳ Exchanging auth_code for tokens...")

    payload = {
        "code": auth_code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data=payload,
    )

    if response.status_code != 200:
        print(f"\n❌ Error: {response.status_code}")
        print(response.text)
        raise RuntimeError("Failed to exchange auth_code for tokens")

    tokens = response.json()
    return tokens


def save_refresh_token(refresh_token: str) -> Path:
    """Save refresh_token to local JSON store."""
    token_store_path = Path(settings.GOOGLE_TOKEN_STORE_PATH)
    token_store_path.parent.mkdir(parents=True, exist_ok=True)

    data = {"refresh_token": refresh_token}
    token_store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Restrict file permissions (Unix-like systems)
    try:
        token_store_path.chmod(0o600)
    except (OSError, NotImplementedError):
        # Permissions not supported on this system (e.g., Windows)
        pass

    return token_store_path


def main():
    """Run the full OAuth setup flow."""
    try:
        # Validate required settings
        if not all([settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET, settings.GOOGLE_REDIRECT_URI]):
            raise ValueError(
                "Missing required environment variables:\n"
                "  - GOOGLE_CLIENT_ID\n"
                "  - GOOGLE_CLIENT_SECRET\n"
                "  - GOOGLE_REDIRECT_URI"
            )

        # Get auth_code from user
        auth_code = get_auth_code()

        # Exchange for tokens
        tokens = exchange_auth_code_for_tokens(auth_code)

        # Save refresh_token
        token_path = save_refresh_token(tokens["refresh_token"])

        print("\n✅ Success!")
        print(f"   Refresh token saved to: {token_path}")
        print(f"   Access token expires in: {tokens.get('expires_in', 'N/A')} seconds")
        print("\n💡 You can now use google_health_access.py to interact with Google Health API.")

    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        raise


if __name__ == "__main__":
    main()
