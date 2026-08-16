"""Interactive Withings authorization via the public Worker relay."""

from __future__ import annotations

import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from kaloriekassen.withings.auth import (
    exchange_authorization_code,
    load_client_secrets,
)


AUTHORIZE_URL = "https://account.withings.com/oauth2_user/authorize2"


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - method name is defined by BaseHTTPRequestHandler
        query = parse_qs(urlparse(self.path).query)
        self.server.oauth_query = query  # type: ignore[attr-defined]
        ok = "code" in query
        message = (
            "Withings-godkendelsen er gennemført. Du kan lukke dette vindue."
            if ok
            else "Withings-godkendelsen fejlede. Gå tilbage til terminalen."
        )
        body = message.encode("utf-8")
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_oauth_flow() -> str:
    config = load_client_secrets()
    state = secrets.token_urlsafe(32)
    parameters = {
        'response_type': 'code',
        'client_id': config['client_id'],
        'scope': 'user.metrics',
        'redirect_uri': config['redirect_uri'],
        'state': state,
    }
    authorization_url = f"{AUTHORIZE_URL}?{urlencode(parameters)}"

    server = HTTPServer(("127.0.0.1", 8081), _CallbackHandler)
    server.timeout = 180
    print("Åbn denne URL, hvis browseren ikke åbner automatisk:")
    print(authorization_url)
    webbrowser.open(authorization_url)
    server.handle_request()
    server.server_close()

    query = getattr(server, "oauth_query", {})
    returned_state = query.get("state", [None])[0]
    if returned_state != state:
        raise RuntimeError("Withings OAuth state did not match")
    if "error" in query:
        raise RuntimeError(f"Withings authorization failed: {query['error'][0]}")
    code = query.get("code", [None])[0]
    if not code:
        raise RuntimeError("No Withings authorization code was received within 3 minutes")

    tokens = exchange_authorization_code(code)
    return str(tokens["access_token"])
