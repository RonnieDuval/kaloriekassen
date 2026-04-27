"""Integration-style tests for google_health_access module (no mocks)."""

import json

import GOOGLE_HEALTH_API.google_health_access as google_health_access
import settings


def test_get_credentials_returns_real_credentials_object(monkeypatch):
    """get_credentials returns a real Credentials object with expected fields."""
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_ID', 'test_client_id')
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_SECRET', 'test_client_secret')

    creds = google_health_access.get_credentials(
        'test_refresh_token',
        refresh_now=False,
    )

    assert creds.__class__.__module__ == 'google.oauth2.credentials'
    assert creds.__class__.__name__ == 'Credentials'
    assert creds.token_uri == 'https://oauth2.googleapis.com/token'
    assert creds.client_id == 'test_client_id'
    assert creds.client_secret == 'test_client_secret'
    assert creds.refresh_token == 'test_refresh_token'
    assert creds.token is None


def test_get_credentials_uses_environment_settings_without_patching_config(monkeypatch):
    """get_credentials uses settings module values as-is."""
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_ID', 'env_client_id')
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_SECRET', 'env_client_secret')

    creds = google_health_access.get_credentials(
        'test_refresh_token',
        refresh_now=False,
    )

    assert creds.client_id == settings.GOOGLE_CLIENT_ID
    assert creds.client_secret == settings.GOOGLE_CLIENT_SECRET
    assert creds.refresh_token == 'test_refresh_token'


def test__load_refresh_token_returns_none_when_file_missing(tmp_path, monkeypatch):
    """Missing token file returns None."""
    token_path = tmp_path / 'missing.json'
    monkeypatch.setattr(settings, 'GOOGLE_TOKEN_STORE_PATH', str(token_path))

    assert google_health_access._load_refresh_token() is None


def test_get_credentials_loads_token_from_store_when_not_passed(tmp_path, monkeypatch):
    """get_credentials loads stored token when no argument is supplied."""
    token_path = tmp_path / 'secrets' / 'token.json'
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(
        json.dumps({'refresh_token': 'stored_refresh_token'}),
        encoding='utf-8',
    )

    monkeypatch.setattr(settings, 'GOOGLE_TOKEN_STORE_PATH', str(token_path))
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_ID', 'store_client_id')
    monkeypatch.setattr(settings, 'GOOGLE_CLIENT_SECRET', 'store_client_secret')

    creds = google_health_access.get_credentials(refresh_now=False)

    assert creds.refresh_token == 'stored_refresh_token'
    assert creds.client_id == 'store_client_id'
    assert creds.client_secret == 'store_client_secret'


def test_get_credentials_raises_without_any_refresh_token(tmp_path, monkeypatch):
    """get_credentials raises if neither argument nor store has token."""
    token_path = tmp_path / 'secrets' / 'missing.json'
    monkeypatch.setattr(settings, 'GOOGLE_TOKEN_STORE_PATH', str(token_path))

    try:
        google_health_access.get_credentials(refresh_now=False)
        assert False, 'Expected ValueError when no refresh token exists'
    except ValueError as exc:
        assert 'No refresh token available' in str(exc)
