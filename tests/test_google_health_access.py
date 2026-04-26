"""Integration tests for google_health_access module."""
from unittest.mock import Mock, patch, MagicMock
import pytest
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import google_health_access
import settings


def test_get_credentials_with_real_objects():
    """Integration test: get_credentials uses real Credentials objects, not mocks."""
    with patch('google_health_access.Credentials.refresh'):
        with patch.object(settings, 'GOOGLE_CLIENT_ID', 'test_client_id'):
            with patch.object(settings, 'GOOGLE_CLIENT_SECRET', 'test_client_secret'):
                creds = google_health_access.get_credentials('test_refresh_token')
    
    # Verify we get a real Credentials object back, not a MagicMock
    assert isinstance(creds, Credentials)
    assert not isinstance(creds, MagicMock)
    assert creds.refresh_token == 'test_refresh_token'


def test_get_credentials_returns_credentials_with_correct_uri():
    """Integration test: get_credentials sets correct token URI."""
    with patch('google_health_access.Credentials.refresh'):
        with patch.object(settings, 'GOOGLE_CLIENT_ID', 'test_client_id'):
            with patch.object(settings, 'GOOGLE_CLIENT_SECRET', 'test_client_secret'):
                creds = google_health_access.get_credentials('test_refresh_token')
    
    assert creds.token_uri == "https://oauth2.googleapis.com/token"
    assert creds.client_id == 'test_client_id'
    assert creds.client_secret == 'test_client_secret'
    assert creds.refresh_token == 'test_refresh_token'


def test_get_credentials_calls_refresh_when_token_invalid():
    """Integration test: get_credentials calls refresh method on invalid token."""
    with patch('google_health_access.Credentials.refresh') as mock_refresh:
        with patch.object(settings, 'GOOGLE_CLIENT_ID', 'test_client_id'):
            with patch.object(settings, 'GOOGLE_CLIENT_SECRET', 'test_client_secret'):
                # Patch the valid property to return False (token needs refresh)
                with patch.object(Credentials, 'valid', new_callable=lambda: property(lambda self: False)):
                    creds = google_health_access.get_credentials('test_refresh_token')
    
    # Verify refresh was called
    mock_refresh.assert_called()


def test_get_credentials_uses_environment_settings():
    """Integration test: get_credentials uses real settings from environment."""
    # Use real settings from environment (no mocking)
    with patch('google_health_access.Credentials.refresh'):
        creds = google_health_access.get_credentials('test_refresh_token')
        breakpoint()
    
    # Verify that real settings were used from environment
    assert creds.client_id == settings.GOOGLE_CLIENT_ID
    assert creds.client_secret == settings.GOOGLE_CLIENT_SECRET
    assert creds.refresh_token == 'test_refresh_token'
    assert creds.token is None  # Token should be None initially


def test_get_credentials_preserves_all_parameters():
    """Integration test: get_credentials preserves all credential parameters."""
    with patch('google_health_access.Credentials.refresh'):
        with patch.object(settings, 'GOOGLE_CLIENT_ID', 'my_test_id'):
            with patch.object(settings, 'GOOGLE_CLIENT_SECRET', 'my_test_secret'):
                test_token = 'my_test_refresh_token_xyz'
                creds = google_health_access.get_credentials(test_token)
    
    # Verify all parameters are correctly set
    assert creds.refresh_token == test_token
    assert creds.client_id == 'my_test_id'
    assert creds.client_secret == 'my_test_secret'
    assert creds.token == None  # Initial token should be None
    assert creds.token_uri == "https://oauth2.googleapis.com/token"
