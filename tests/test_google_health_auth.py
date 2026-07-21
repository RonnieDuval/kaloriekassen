import json
from unittest.mock import Mock, patch

import pytest
from google.auth.exceptions import RefreshError

from kaloriekassen.google_health.auth import get_credentials
from kaloriekassen.google_health.setup import SCOPES, run_oauth_flow


def write_client_secrets(path):
    path.write_text(json.dumps({
        "web": {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"],
        }
    }))


def test_get_credentials_recovers_from_rejected_refresh_token(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"
    client_path = tmp_path / "client.json"
    token_path.write_text(json.dumps({"refresh_token": "expired"}))
    write_client_secrets(client_path)
    monkeypatch.setenv("GOOGLE_TOKEN_STORE_PATH", str(token_path))
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS_PATH", str(client_path))

    def replace_refresh_token():
        token_path.write_text(json.dumps({"refresh_token": "replacement"}))
        return "new-access-token"

    with patch("kaloriekassen.google_health.auth.Credentials.refresh") as refresh, patch(
        "kaloriekassen.google_health.setup.run_oauth_flow",
        side_effect=replace_refresh_token,
    ) as oauth_flow:
        refresh.side_effect = [RefreshError("invalid_grant"), None]

        credentials = get_credentials()

    oauth_flow.assert_called_once_with()
    assert refresh.call_count == 2
    assert credentials.refresh_token == "replacement"


def test_run_oauth_flow_persists_refresh_token(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"
    client_path = tmp_path / "client.json"
    write_client_secrets(client_path)
    monkeypatch.setenv("GOOGLE_TOKEN_STORE_PATH", str(token_path))
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS_PATH", str(client_path))
    credentials = Mock(token="access-token", refresh_token="replacement-token")

    with patch(
        "kaloriekassen.google_health.setup.InstalledAppFlow.from_client_secrets_file"
    ) as from_client_secrets_file:
        from_client_secrets_file.return_value.run_local_server.return_value = credentials

        assert run_oauth_flow() == "access-token"

    assert json.loads(token_path.read_text()) == {"refresh_token": "replacement-token"}
    from_client_secrets_file.assert_called_once_with(str(client_path), scopes=SCOPES)
    from_client_secrets_file.return_value.run_local_server.assert_called_once_with(
        host="localhost", port=8080, prompt="consent", access_type="offline"
    )


def test_run_oauth_flow_requires_refresh_token(tmp_path, monkeypatch):
    client_path = tmp_path / "client.json"
    write_client_secrets(client_path)
    monkeypatch.setenv("GOOGLE_TOKEN_STORE_PATH", str(tmp_path / "token.json"))
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS_PATH", str(client_path))

    with patch(
        "kaloriekassen.google_health.setup.InstalledAppFlow.from_client_secrets_file"
    ) as from_client_secrets_file:
        from_client_secrets_file.return_value.run_local_server.return_value = Mock(
            refresh_token=None
        )
        with pytest.raises(RuntimeError, match="without a refresh token"):
            run_oauth_flow()
