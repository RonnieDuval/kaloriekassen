from unittest.mock import Mock, patch

from kaloriekassen.integrations.google_health.reader import fetch_exercises


@patch("kaloriekassen.integrations.google_health.reader.requests.get")
def test_fetch_exercises_only_performs_get(request_get):
    response = Mock()
    response.json.return_value = {"dataPoints": [{"name": "exercise/1"}]}
    request_get.return_value = response

    assert fetch_exercises("token") == [{"name": "exercise/1"}]
    request_get.assert_called_once()
    response.raise_for_status.assert_called_once()
