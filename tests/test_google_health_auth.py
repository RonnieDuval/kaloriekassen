import json
from unittest.mock import Mock, patch

import pytest
from google.auth.exceptions import RefreshError

from kaloriekassen.integrations.google_health.auth import get_credentials
from kaloriekassen.integrations.google_health.setup import run_oauth_flow


def test_get_credentials_recovers_from_rejected_refresh_token(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"refresh_token": "expired"}))
    monkeypatch.setenv("GOOGLE_TOKEN_STORE_PATH", str(token_path))
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    def replace_refresh_token():
        token_path.write_text(json.dumps({"refresh_token": "replacement"}))
        return "new-access-token"

    with patch("kaloriekassen.integrations.google_health.auth.Credentials.refresh") as refresh, patch(
        "kaloriekassen.integrations.google_health.setup.run_oauth_flow",
        side_effect=replace_refresh_token,
    ) as oauth_flow:
        refresh.side_effect = [RefreshError("invalid_grant"), None]

        credentials = get_credentials()

    oauth_flow.assert_called_once_with()
    assert refresh.call_count == 2
    assert credentials.refresh_token == "replacement"


def test_run_oauth_flow_persists_refresh_token(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"
    monkeypatch.setenv("GOOGLE_TOKEN_STORE_PATH", str(token_path))
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    credentials = Mock(token="access-token", refresh_token="replacement-token")

    with patch(
        "kaloriekassen.integrations.google_health.setup.InstalledAppFlow.from_client_config"
    ) as from_client_config:
        from_client_config.return_value.run_local_server.return_value = credentials

        assert run_oauth_flow() == "access-token"

    assert json.loads(token_path.read_text()) == {"refresh_token": "replacement-token"}
    from_client_config.return_value.run_local_server.assert_called_once_with(
        host="localhost", port=8080, prompt="consent", access_type="offline"
    )


def test_run_oauth_flow_requires_refresh_token(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_TOKEN_STORE_PATH", str(tmp_path / "token.json"))
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")

    with patch(
        "kaloriekassen.integrations.google_health.setup.InstalledAppFlow.from_client_config"
    ) as from_client_config:
        from_client_config.return_value.run_local_server.return_value = Mock(
            refresh_token=None
        )
        with pytest.raises(RuntimeError, match="without a refresh token"):
            run_oauth_flow()
