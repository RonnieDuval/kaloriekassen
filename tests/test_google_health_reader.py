from unittest.mock import Mock, patch

from kaloriekassen.integrations.google_health.reader import (
    GOOGLE_HEALTH_NUTRITION_LOG_ENDPOINT,
    fetch_exercises,
    fetch_nutrition_logs,
)


@patch("kaloriekassen.integrations.google_health.reader.requests.get")
def test_fetch_exercises_only_performs_get(request_get):
    response = Mock()
    response.json.return_value = {"dataPoints": [{"name": "exercise/1"}]}
    request_get.return_value = response

    assert fetch_exercises("token") == [{"name": "exercise/1"}]
    request_get.assert_called_once()
    response.raise_for_status.assert_called_once()


@patch("kaloriekassen.integrations.google_health.reader.requests.get")
def test_fetch_nutrition_logs_uses_nutrition_endpoint_and_filter(request_get):
    response = Mock()
    response.json.return_value = {"dataPoints": [{"name": "nutrition-log/1"}]}
    request_get.return_value = response
    filter_expression = (
        'nutrition_log.interval.civil_start_time >= "2026-07-20" AND '
        'nutrition_log.interval.civil_start_time < "2026-07-21"'
    )

    assert fetch_nutrition_logs("token", page_size=50, filter_expression=filter_expression) == [
        {"name": "nutrition-log/1"}
    ]
    request_get.assert_called_once_with(
        GOOGLE_HEALTH_NUTRITION_LOG_ENDPOINT,
        headers={"Authorization": "Bearer token", "Accept": "application/json"},
        params={"pageSize": 50, "filter": filter_expression},
        timeout=30,
    )
    response.raise_for_status.assert_called_once()


@patch("kaloriekassen.integrations.google_health.reader.requests.get")
def test_fetch_nutrition_logs_follows_pagination(request_get):
    first_response = Mock()
    first_response.json.return_value = {
        "dataPoints": [{"name": "nutrition-log/1"}],
        "nextPageToken": "next-page",
    }
    second_response = Mock()
    second_response.json.return_value = {
        "dataPoints": [{"name": "nutrition-log/2"}],
    }
    request_get.side_effect = [first_response, second_response]

    assert fetch_nutrition_logs("token") == [
        {"name": "nutrition-log/1"},
        {"name": "nutrition-log/2"},
    ]
    assert request_get.call_count == 2
    assert request_get.call_args_list[1].kwargs["params"] == {
        "pageSize": 100,
        "pageToken": "next-page",
    }
    first_response.raise_for_status.assert_called_once()
    second_response.raise_for_status.assert_called_once()
