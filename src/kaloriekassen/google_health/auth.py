"""Google Health OAuth credential helpers.

The downloaded OAuth client configuration and the generated refresh token are
stored as separate, ignored files under ``secrets/``.
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


class GoogleOAuthReauthorizationRequired(RuntimeError):
    """Raised when headless operation requires a new interactive grant."""


def _interactive_oauth_enabled() -> bool:
    value = os.getenv("GOOGLE_OAUTH_INTERACTIVE", "true").strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError("GOOGLE_OAUTH_INTERACTIVE must be true or false")


def _token_store_path() -> Path:
    """Return path to local token store file."""
    return Path(os.getenv("GOOGLE_TOKEN_STORE_PATH", "secrets/google_oauth_token.json"))


def _client_secrets_path() -> Path:
    """Return the downloaded Google Cloud OAuth client configuration path."""
    return Path(
        os.getenv(
            "GOOGLE_CLIENT_SECRETS_PATH",
            "secrets/google_api_client_secrets.json",
        )
    )


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
    """Load the active OAuth client section from Google's downloaded JSON."""
    path = _client_secrets_path()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(
            f"Google OAuth client file not found: {path}. "
            "Download it from Google Cloud Console."
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid Google OAuth client file: {path}") from error

    client = document.get("installed") or document.get("web")
    required_fields = {"client_id", "client_secret", "token_uri"}
    if not isinstance(client, dict) or not required_fields.issubset(client):
        raise ValueError(
            "Google OAuth client file must contain a valid 'installed' or 'web' section"
        )
    return client


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
        token_uri=client_secrets["token_uri"],
        client_id=client_secrets["client_id"],
        client_secret=client_secrets["client_secret"],
    )

    if refresh_now and not creds.valid:
        try:
            creds.refresh(Request())
        except RefreshError:
            if not _interactive_oauth_enabled():
                raise GoogleOAuthReauthorizationRequired(
                    "Google rejected the stored refresh token. Run "
                    "'kaloriekassen google-health-auth' on a computer with a "
                    "browser and replace secrets/google_oauth_token.json."
                )
            logger.warning(
                "Google rejected the stored refresh token; starting the OAuth recovery flow."
            )
            # Import lazily: setup needs the client-secret helper in this module.
            from kaloriekassen.google_health.setup import run_oauth_flow

            run_oauth_flow()
            # The interactive flow persisted a replacement token. Rebuild the
            # credentials and refresh it so callers retain the normal contract.
            return get_credentials(refresh_now=refresh_now)

    return creds
