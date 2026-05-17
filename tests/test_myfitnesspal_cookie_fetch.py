"""Tests for MyFitnessPal package-backed cookie nutrition fetch."""
import datetime as dt
from unittest.mock import Mock, patch

import pytest

from MYFITNESSPAL import hent_mfp_data


def test_create_mfp_client_uses_package_cookie_handling_by_default(monkeypatch):
    """Without injected env cookies, myfitnesspal.Client loads its own cookies."""
    monkeypatch.setattr(hent_mfp_data.settings, "MFP_COOKIE_B", "")
    monkeypatch.setattr(hent_mfp_data.settings, "MFP_COOKIE_SESSION", "")

    client = object()
    with patch.object(hent_mfp_data.myfitnesspal, "Client", return_value=client) as client_cls:
        assert hent_mfp_data.create_mfp_client() is client

    client_cls.assert_called_once_with()


def test_build_injected_mfp_cookiejar_uses_myfitnesspal_cookie_domains():
    """Injected cookies are adapted to the CookieJar shape the package accepts."""
    cookiejar = hent_mfp_data.build_injected_mfp_cookiejar(
        "cookie-b",
        "session-cookie",
    )

    for domain in hent_mfp_data.myfitnesspal.Client.COOKIE_DOMAINS:
        assert cookiejar.get("b", domain=domain, path="/") == "cookie-b"
        assert (
            cookiejar.get("user_session", domain=domain, path="/")
            == "session-cookie"
        )


def test_build_injected_mfp_cookiejar_requires_both_cookies(monkeypatch):
    """Partial injected cookie configuration fails before calling MyFitnessPal."""
    monkeypatch.setattr(hent_mfp_data.settings, "MFP_COOKIE_B", "")
    monkeypatch.setattr(hent_mfp_data.settings, "MFP_COOKIE_SESSION", "session-cookie")

    with pytest.raises(ValueError, match="MFP_COOKIE_B og MFP_COOKIE_SESSION"):
        hent_mfp_data.build_injected_mfp_cookiejar()


def test_create_mfp_client_can_use_injected_cookiejar(monkeypatch):
    """Docker/env cookies are passed as a cookiejar to the myfitnesspal package."""
    cookiejar = object()
    client = object()

    monkeypatch.setattr(hent_mfp_data.settings, "MFP_COOKIE_B", "cookie-b")
    monkeypatch.setattr(hent_mfp_data.settings, "MFP_COOKIE_SESSION", "session-cookie")
    monkeypatch.setattr(
        hent_mfp_data,
        "build_injected_mfp_cookiejar",
        Mock(return_value=cookiejar),
    )

    with patch.object(hent_mfp_data.myfitnesspal, "Client", return_value=client) as client_cls:
        assert hent_mfp_data.create_mfp_client() is client

    client_cls.assert_called_once_with(cookiejar=cookiejar)


def test_build_nutrition_payload_maps_totals_to_project_payload():
    """MFP total keys are normalized to the project's nutrition payload."""
    payload = hent_mfp_data.build_nutrition_payload(
        dt.date(2026, 5, 17),
        {
            "calories": "2100",
            "protein": "150",
            "carbohydrates": "240",
            "fat": "70",
        },
    )

    assert payload == {
        "date": "2026-05-17",
        "calories": 2100,
        "protein": 150,
        "carbohydrates": 240,
        "fat": 70,
    }


def test_hent_nutrition_data_uses_myfitnesspal_client(monkeypatch):
    """The fetch uses the package client factory and returns mapped totals."""
    target_day = dt.date(2026, 5, 17)
    diary = Mock(totals={"calories": 1800, "protein": 120})
    client = Mock()
    client.get_date.return_value = diary

    monkeypatch.setattr(hent_mfp_data, "create_mfp_client", Mock(return_value=client))

    payload = hent_mfp_data.hent_nutrition_data(target_day)

    hent_mfp_data.create_mfp_client.assert_called_once_with()
    client.get_date.assert_called_once_with(target_day)
    assert payload == {
        "date": "2026-05-17",
        "calories": 1800,
        "protein": 120,
        "carbohydrates": 0,
        "fat": 0,
    }
