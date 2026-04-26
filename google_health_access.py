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

import settings


def _token_store_path() -> Path:
    """Return path to local token store file."""
    return Path(settings.GOOGLE_TOKEN_STORE_PATH)


def load_refresh_token() -> Optional[str]:
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


def save_refresh_token(refresh_token: str) -> None:
    """Persist refresh token to local JSON store.

    The parent directory is created automatically.
    """
    token_path = _token_store_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"refresh_token": refresh_token}
    token_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_credentials(
    refresh_token: Optional[str] = None,
    *,
    refresh_now: bool = True,
) -> Credentials:
    """Build credentials and refresh access token when needed.

    If refresh_token is not provided, it is loaded from the local token store.
    Set refresh_now=False to skip immediate refresh (useful for offline tests).
    """
    token = refresh_token or load_refresh_token()
    if not token:
        raise ValueError(
            "No refresh token available. Run OAuth flow and save token first."
        )

    creds = Credentials(
        token=None,
        refresh_token=token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    if refresh_now and not creds.valid:
        creds.refresh(Request())

    return creds
