from unittest.mock import Mock, patch

import pytest

from kaloriekassen.myfitnesspal import client


def test_parse_food_rows_parses_meals_and_skips_controls():
    html = """
    <table class="table0"><tbody>
      <tr class="meal_header"><td>Breakfast</td></tr>
      <tr><td>Oatmeal</td><td>250</td><td>42</td><td>5</td><td>8</td><td>10</td><td>2</td></tr>
      <tr><td>Add Food</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
      <tr class="total"><td>Total</td><td>250</td></tr>
    </tbody></table>
    """

    assert client.parse_food_rows(html, "2026-07-20") == {
        "date": "2026-07-20",
        "meals": {
            "Breakfast": [
                {
                    "name": "Oatmeal",
                    "calories": 250,
                    "carbohydrates": 42,
                    "fat": 5,
                    "protein": 8,
                    "sodium": 10,
                    "sugar": 2,
                }
            ]
        },
    }


def test_hent_mfp_dag_requires_a_manually_created_session(monkeypatch):
    monkeypatch.delenv(client.COOKIE_HEADER_ENV_VAR, raising=False)

    with pytest.raises(client.MyFitnessPalAuthenticationError, match="MFP_COOKIE_HEADER"):
        client.hent_mfp_dag("2026-07-20")


@patch("kaloriekassen.myfitnesspal.client.requests.get")
def test_hent_mfp_dag_uses_cookie_header_and_rejects_login_page(request_get, monkeypatch):
    monkeypatch.setenv(client.COOKIE_HEADER_ENV_VAR, "Cookie: user_session=secret")
    response = Mock(url="https://www.myfitnesspal.com/login", text="login")
    request_get.return_value = response

    with pytest.raises(
        client.MyFitnessPalAuthenticationError,
        match="Svar-URL: https://www.myfitnesspal.com/login.*user_session",
    ):
        client.hent_mfp_dag("2026-07-20")

    request_get.assert_called_once()
    assert request_get.call_args.kwargs["headers"]["Cookie"] == "user_session=secret"


def test_cookie_names_excludes_cookie_values():
    assert client._cookie_names("euconsent-v2=secret; user_session=another-secret") == [
        "euconsent-v2",
        "user_session",
    ]


@patch("kaloriekassen.myfitnesspal.client.requests.get")
def test_hent_mfp_dag_does_not_treat_a_recaptcha_script_as_a_login_page(request_get, monkeypatch):
    monkeypatch.setenv(client.COOKIE_HEADER_ENV_VAR, "user_session=secret")
    response = Mock(
        url="https://www.myfitnesspal.com/food/diary?date=2026-07-20",
        text="""
        <script src=\"https://www.google.com/recaptcha/api.js\"></script>
        <table class=\"table0\"><tbody>
          <tr class=\"meal_header\"><td>Breakfast</td></tr>
          <tr><td>Oatmeal</td><td>250</td><td>42</td><td>5</td><td>8</td></tr>
        </tbody></table>
        """,
    )
    request_get.return_value = response

    assert client.hent_mfp_dag("2026-07-20")["meals"]["Breakfast"][0]["name"] == "Oatmeal"


@patch("kaloriekassen.myfitnesspal.client.requests.get")
def test_hent_mfp_dag_does_not_treat_diary_password_ui_as_a_login_page(request_get, monkeypatch):
    monkeypatch.setenv(client.COOKIE_HEADER_ENV_VAR, "_mfp_session=secret")
    response = Mock(
        url="https://www.myfitnesspal.com/food/diary?date=2026-07-20",
        text="""
        <input type="password" name="password" />
        <table class="table0"><tbody>
          <tr class="meal_header"><td>Breakfast</td></tr>
          <tr><td>Oatmeal</td><td>250</td><td>42</td><td>5</td><td>8</td></tr>
        </tbody></table>
        """,
    )
    request_get.return_value = response

    assert client.hent_mfp_dag("2026-07-20")["meals"]["Breakfast"][0]["name"] == "Oatmeal"
