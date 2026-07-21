"""Google Health OAuth credential helpers.

Level 1 token storage:
- Keep static app config (client id/secret) in environment variables.
- Persist refresh token in a local JSON file under ./secrets.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from dotenv import load_dotenv

import os


load_dotenv()

logger = logging.getLogger(__name__)


def _token_store_path() -> Path:
    """Return path to local token store file."""
    return Path(os.getenv("GOOGLE_TOKEN_STORE_PATH", "secrets/google_oauth_token.json"))


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
    """Load OAuth application credentials from the environment."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured")
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
        except RefreshError:
            logger.warning(
                "Google rejected the stored refresh token; starting the OAuth recovery flow."
            )
            # Import lazily: setup needs the client-secret helper in this module.
            from kaloriekassen.integrations.google_health.setup import run_oauth_flow

            run_oauth_flow()
            # The interactive flow persisted a replacement token. Rebuild the
            # credentials and refresh it so callers retain the normal contract.
            return get_credentials(refresh_now=refresh_now)

    return creds
