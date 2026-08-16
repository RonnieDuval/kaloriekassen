from datetime import date
from unittest.mock import Mock, call, patch

from kaloriekassen.google_health.reader import (
    GOOGLE_HEALTH_EXERCISE_ENDPOINT,
    GOOGLE_HEALTH_NUTRITION_LOG_ENDPOINT,
    fetch_daily_rollups,
    fetch_exercises,
    fetch_nutrition_logs,
)


@patch("kaloriekassen.google_health.reader.requests.post")
def test_fetch_daily_rollups_uses_civil_dates_and_pagination(request_post):
    first_response = Mock()
    first_response.json.return_value = {
        "rollupDataPoints": [{"steps": {"countSum": "4000"}}],
        "nextPageToken": "next-page",
    }
    second_response = Mock()
    second_response.json.return_value = {
        "rollupDataPoints": [{"steps": {"countSum": "5000"}}],
    }
    request_post.side_effect = [first_response, second_response]

    assert fetch_daily_rollups(
        "token",
        "steps",
        date(2026, 8, 13),
        date(2026, 8, 15),
    ) == [
        {"steps": {"countSum": "4000"}},
        {"steps": {"countSum": "5000"}},
    ]
    first_body = request_post.call_args_list[0].kwargs["json"]
    second_body = request_post.call_args_list[1].kwargs["json"]
    assert first_body["range"]["start"]["date"] == {
        "year": 2026,
        "month": 8,
        "day": 13,
    }
    assert first_body["range"]["end"]["date"] == {
        "year": 2026,
        "month": 8,
        "day": 15,
    }
    assert first_body["windowSizeDays"] == 1
    assert second_body["pageToken"] == "next-page"
    assert request_post.call_args_list[0].args[0].endswith(
        "/steps/dataPoints:dailyRollUp"
    )


def test_fetch_daily_rollups_rejects_empty_range():
    try:
        fetch_daily_rollups(
            "token",
            "steps",
            date(2026, 8, 15),
            date(2026, 8, 15),
        )
    except ValueError as error:
        assert str(error) == "end_date must be after start_date"
    else:
        raise AssertionError("Expected invalid date range to fail")


@patch("kaloriekassen.google_health.reader.requests.get")
def test_fetch_exercises_only_performs_get(request_get):
    response = Mock()
    response.json.return_value = {"dataPoints": [{"name": "exercise/1"}]}
    request_get.return_value = response

    assert fetch_exercises("token") == [{"name": "exercise/1"}]
    request_get.assert_called_once_with(
        GOOGLE_HEALTH_EXERCISE_ENDPOINT,
        headers={"Authorization": "Bearer token", "Accept": "application/json"},
        params={"pageSize": 25},
        timeout=30,
    )
    response.raise_for_status.assert_called_once()


@patch("kaloriekassen.google_health.reader.requests.get")
def test_fetch_exercises_follows_pagination(request_get):
    first_response = Mock()
    first_response.json.return_value = {
        "dataPoints": [{"name": "exercise/1"}],
        "nextPageToken": "next-page",
    }
    second_response = Mock()
    second_response.json.return_value = {
        "dataPoints": [{"name": "exercise/2"}],
    }
    request_get.side_effect = [first_response, second_response]

    assert fetch_exercises("token", page_size=50) == [
        {"name": "exercise/1"},
        {"name": "exercise/2"},
    ]
    request_get.assert_has_calls(
        [
            call(
                GOOGLE_HEALTH_EXERCISE_ENDPOINT,
                headers={"Authorization": "Bearer token", "Accept": "application/json"},
                params={"pageSize": 50},
                timeout=30,
            ),
            call(
                GOOGLE_HEALTH_EXERCISE_ENDPOINT,
                headers={"Authorization": "Bearer token", "Accept": "application/json"},
                params={"pageSize": 50, "pageToken": "next-page"},
                timeout=30,
            ),
        ]
    )
    first_response.raise_for_status.assert_called_once()
    second_response.raise_for_status.assert_called_once()


@patch("kaloriekassen.google_health.reader.requests.get")
def test_fetch_exercises_passes_date_filter(request_get):
    response = Mock()
    response.json.return_value = {"dataPoints": []}
    request_get.return_value = response
    filter_expression = (
        'exercise.interval.civil_start_time >= "2026-08-14T00:00:00" AND '
        'exercise.interval.civil_start_time < "2026-08-17T00:00:00"'
    )

    assert fetch_exercises("token", filter_expression=filter_expression) == []
    assert request_get.call_args.kwargs["params"] == {
        "pageSize": 25,
        "filter": filter_expression,
    }


@patch("kaloriekassen.google_health.reader.requests.get")
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


@patch("kaloriekassen.google_health.reader.requests.get")
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
