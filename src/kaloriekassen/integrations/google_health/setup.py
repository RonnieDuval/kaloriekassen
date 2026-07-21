"""Interactive OAuth recovery for Google Health credentials."""
from __future__ import annotations

import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from kaloriekassen.integrations.google_health.auth import _load_client_secrets


SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.writeonly",
    "https://www.googleapis.com/auth/googlehealth.nutrition.readonly",
]


def run_oauth_flow() -> str:
    """Open a browser, obtain a replacement refresh token, and persist it.

    This is used automatically after Google rejects the stored refresh token. It
    can also be invoked explicitly through ``kaloriekassen google-health-auth``.
    The OAuth client must be configured as a desktop application and permit the
    local redirect URI used by :meth:`InstalledAppFlow.run_local_server`.
    """
    client_secrets = _load_client_secrets()
    client_config = {
        "installed": {
            **client_secrets,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    credentials = flow.run_local_server(
        host="localhost",
        port=8080,
        prompt="consent",
        access_type="offline",
    )

    if not credentials.refresh_token:
        raise RuntimeError("Google OAuth flow completed without a refresh token")

    token_path = Path(
        os.getenv("GOOGLE_TOKEN_STORE_PATH", "secrets/google_oauth_token.json")
    )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(
        json.dumps({"refresh_token": credentials.refresh_token}, indent=2),
        encoding="utf-8",
    )
    try:
        token_path.chmod(0o600)
    except OSError:
        # Windows does not support POSIX file modes. The user profile ACL still
        # protects the file there.
        pass

    return credentials.token
