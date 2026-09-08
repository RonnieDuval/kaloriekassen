"""Withings OAuth signing, token exchange, refresh, and local token storage."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any

import requests


API_BASE_URL = "https://wbsapi.withings.net"


class WithingsApiError(RuntimeError):
    """A Withings API response reported an error."""


def _client_secrets_path() -> Path:
    return Path(
        os.getenv("WITHINGS_CLIENT_SECRETS_PATH", "secrets/withings_api_client.json")
    )


def _token_store_path() -> Path:
    return Path(os.getenv("WITHINGS_TOKEN_STORE_PATH", "secrets/withings_oauth_token.json"))


def load_client_secrets() -> dict[str, str]:
    path = _client_secrets_path()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(
            f"Withings OAuth client file not found: {path}. See README.md for setup."
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid Withings OAuth client file: {path}") from error

    required = ("client_id", "client_secret", "redirect_uri")
    if not isinstance(config, dict) or any(
        not isinstance(config.get(key), str) or not config[key] for key in required
    ):
        raise ValueError(
            "Withings OAuth client file must contain client_id, client_secret, "
            "and redirect_uri"
        )
    return {key: config[key] for key in required}


def load_tokens() -> dict[str, Any]:
    path = _token_store_path()
    try:
        tokens = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError("No Withings tokens found. Run: kaloriekassen withings-auth") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid Withings token file: {path}") from error
    if not isinstance(tokens, dict) or not tokens.get("refresh_token"):
        raise ValueError(f"Withings token file has no refresh_token: {path}")
    return tokens


def save_tokens(tokens: dict[str, Any]) -> None:
    """Atomically replace the token file so rotating refresh tokens are not lost."""
    path = _token_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def _signature(values: dict[str, Any], client_secret: str) -> str:
    message = ",".join(str(values[key]) for key in sorted(values))
    return hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _response_body(response: requests.Response) -> dict[str, Any]:
    response.raise_for_status()
    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as error:
        raise WithingsApiError("Withings returned an invalid JSON response") from error
    if not isinstance(payload, dict) or payload.get("status") != 0:
        status = payload.get("status") if isinstance(payload, dict) else "unknown"
        raise WithingsApiError(f"Withings API returned status {status}")
    body = payload.get("body")
    if not isinstance(body, dict):
        raise WithingsApiError("Withings response is missing its body")
    return body


def get_nonce(client_id: str, client_secret: str) -> str:
    timestamp = int(time.time())
    signed = {"action": "getnonce", "client_id": client_id, "timestamp": timestamp}
    body = _response_body(
        requests.post(
            f"{API_BASE_URL}/v2/signature",
            data={**signed, "signature": _signature(signed, client_secret)},
            timeout=30,
        )
    )
    nonce = body.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        raise WithingsApiError("Withings response is missing its nonce")
    return nonce


def _request_tokens(extra: dict[str, str], config: dict[str, str]) -> dict[str, Any]:
    nonce = get_nonce(config["client_id"], config["client_secret"])
    signed = {"action": "requesttoken", "client_id": config["client_id"], "nonce": nonce}
    body = _response_body(
        requests.post(
            f"{API_BASE_URL}/v2/oauth2",
            data={
                **signed,
                **extra,
                "signature": _signature(signed, config["client_secret"]),
            },
            timeout=30,
        )
    )
    if not body.get("access_token") or not body.get("refresh_token"):
        raise WithingsApiError("Withings token response is incomplete")
    expires_in = int(body.get("expires_in", 10800))
    return {**body, "expires_at": int(time.time()) + expires_in}


def exchange_authorization_code(code: str) -> dict[str, Any]:
    config = load_client_secrets()
    tokens = _request_tokens(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
        },
        config,
    )
    save_tokens(tokens)
    return tokens


def refresh_tokens(refresh_token: str | None = None) -> dict[str, Any]:
    config = load_client_secrets()
    current = load_tokens() if refresh_token is None else {"refresh_token": refresh_token}
    tokens = _request_tokens(
        {"grant_type": "refresh_token", "refresh_token": current["refresh_token"]},
        config,
    )
    save_tokens(tokens)
    return tokens


def get_access_token() -> str:
    tokens = load_tokens()
    if not tokens.get("access_token") or int(tokens.get("expires_at", 0)) <= int(time.time()) + 60:
        tokens = refresh_tokens(tokens["refresh_token"])
    return str(tokens["access_token"])
