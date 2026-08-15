import hashlib
import hmac

from kaloriekassen.withings import auth


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_signature_sorts_values_by_parameter_name():
    values = {"timestamp": 123, "action": "getnonce", "client_id": "client"}
    expected = hmac.new(
        b"secret", b"getnonce,client,123", hashlib.sha256
    ).hexdigest()

    assert auth._signature(values, "secret") == expected


def test_exchange_code_signs_request_and_saves_tokens(monkeypatch):
    posts = []
    saved = []
    config = {
        "client_id": "client",
        "client_secret": "secret",
        "redirect_uri": "https://relay.example/oauth/callback",
    }

    def post(url, data, timeout):
        posts.append((url, data, timeout))
        return _Response(
            {
                "status": 0,
                "body": {
                    "access_token": "access",
                    "refresh_token": "refresh",
                    "expires_in": 10800,
                },
            }
        )

    monkeypatch.setattr(auth, "load_client_secrets", lambda: config)
    monkeypatch.setattr(auth, "get_nonce", lambda *_: "nonce")
    monkeypatch.setattr(auth.requests, "post", post)
    monkeypatch.setattr(auth, "save_tokens", saved.append)
    monkeypatch.setattr(auth.time, "time", lambda: 1000)

    result = auth.exchange_authorization_code("short-code")

    assert result["expires_at"] == 11800
    assert saved == [result]
    assert posts[0][0].endswith("/v2/oauth2")
    assert posts[0][1]["grant_type"] == "authorization_code"
    assert posts[0][1]["redirect_uri"] == config["redirect_uri"]
    assert posts[0][1]["code"] == "short-code"
    assert posts[0][1]["nonce"] == "nonce"


def test_expired_access_token_is_refreshed(monkeypatch):
    monkeypatch.setattr(
        auth,
        "load_tokens",
        lambda: {"access_token": "old", "refresh_token": "rotate", "expires_at": 1},
    )
    monkeypatch.setattr(
        auth,
        "refresh_tokens",
        lambda token: {"access_token": "new", "refresh_token": "new-refresh"},
    )

    assert auth.get_access_token() == "new"
