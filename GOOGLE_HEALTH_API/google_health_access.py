"""Google Health OAuth credential helpers.

Level 1 token storage:
- Keep static app config (client id/secret) in environment variables.
- Persist refresh token in a local JSON file under ./secrets.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError

import settings


def _token_store_path() -> Path:
    """Return path to local token store file."""
    return Path(settings.GOOGLE_TOKEN_STORE_PATH)


def _load_refresh_token() -> Optional[str]:
    """Load refresh token from local JSON store.

    Returns None when token store is missing or malformed.
    """
    token_path = _token_store_path()

    if not token_path.exists():
        return None

    try:
        data = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    token = data.get("refresh_token")
    return token if isinstance(token, str) and token else None


def _load_client_secrets() -> dict:
    """Load client ID and client secret from google_api_client_secrets2.json."""
    secrets_path = Path(__file__).parent.parent / "google_api_client_secrets2.json"
    if not secrets_path.exists():
        raise FileNotFoundError(f"Client secrets file not found: {secrets_path}")

    try:
        data = json.loads(secrets_path.read_text(encoding="utf-8"))
        # Assuming the structure is for a 'web' application, adjust if 'installed'
        if "web" in data:
            client_id = data["web"]["client_id"]
            client_secret = data["web"]["client_secret"]
        elif "installed" in data:
            client_id = data["installed"]["client_id"]
            client_secret = data["installed"]["client_secret"]
        else:
            raise ValueError("Invalid client secrets file format.")
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Failed to parse client secrets file: {e}")

    return {"client_id": client_id, "client_secret": client_secret}


def get_credentials(
    refresh_token: Optional[str] = None,
    *,
    refresh_now: bool = True,
) -> Credentials:
    """Build credentials and refresh access token when needed.

    If refresh_token is not provided, it is loaded from the local token store.
    Set refresh_now=False to skip immediate refresh (useful for offline tests).
    """
    token = refresh_token or _load_refresh_token()
    if not token:
        raise ValueError(
            "No refresh token available. Run OAuth flow and save token first."
        )

    client_secrets = _load_client_secrets()
    creds = Credentials(
        token=None,
        refresh_token=token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_secrets["client_id"],
        client_secret=client_secrets["client_secret"],
    )

    if refresh_now and not creds.valid:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise RefreshError(f"Google credentials have expired or been revoked: {e}")

    return creds