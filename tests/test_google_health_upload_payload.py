from unittest.mock import Mock, patch

from kaloriekassen.google_health.client import (
    GOOGLE_HEALTH_EXERCISE_ENDPOINT,
    patch_exercise_record,
    upload_exercise_records,
)
from kaloriekassen.google_health.mapper import (
    map_single_activity_to_google_exercise,
)


def test_mapped_activity_is_sent_unchanged_to_google_health_api():
    activity = {
        "id": "intervals-activity-123",
        "start_date": "2026-07-20T08:00:00Z",
        "start_date_local": "2026-07-20T10:00:00",
        "timezone": "Europe/Copenhagen",
        "elapsed_time": 3600,
        "type": "Ride",
        "calories": 500,
        "distance": 20_000,
        "total_elevation_gain": 125,
        "average_heartrate": 164,
    }
    expected_payload = {
        "exercise": {
            "interval": {
                "startTime": "2026-07-20T10:00:00+02:00",
                "startUtcOffset": "7200s",
                "endTime": "2026-07-20T11:00:00+02:00",
                "endUtcOffset": "7200s",
            },
            "exerciseType": "BIKING",
            "metricsSummary": {
                "caloriesKcal": 500.0,
                "distanceMillimeters": 20_000_000,
                "elevationGainMillimeters": 125_000,
                "averageHeartRateBeatsPerMinute": "164",
            },
            "displayName": "BIKING: 20.0km",
            "activeDuration": "3600s",
        },
        "dataSource": {
            "application": {"packageName": "com.intervals.icu"},
            "recordingMethod": "ACTIVELY_MEASURED",
        },
    }
    mapped_payload = map_single_activity_to_google_exercise(activity)
    response = Mock(status_code=201)
    response.json.return_value = {"name": "exercise/dataPoints/google-123"}

    with patch(
        "kaloriekassen.google_health.client.requests.post",
        return_value=response,
    ) as request_post:
        result = upload_exercise_records("access-token", [mapped_payload])

    assert mapped_payload == expected_payload
    request_post.assert_called_once_with(
        GOOGLE_HEALTH_EXERCISE_ENDPOINT,
        headers={
            "Authorization": "Bearer access-token",
            "Content-Type": "application/json",
        },
        json=expected_payload,
        timeout=30,
    )
    assert result == {
        "successful": [{
            "date": "2026-07-20",
            "google_health_id": "exercise/dataPoints/google-123",
        }],
        "failed": [],
        "total": 1,
    }


def test_patch_updates_existing_exercise_without_creating_a_new_one():
    google_id = "users/1/dataTypes/exercise/dataPoints/1234"
    data_point = {
        "exercise": {
            "metricsSummary": {"averageHeartRateBeatsPerMinute": "164"}
        },
        "dataSource": {"recordingMethod": "ACTIVELY_MEASURED"},
    }
    response = Mock(status_code=200)

    with patch(
        "kaloriekassen.google_health.client.requests.patch",
        return_value=response,
    ) as request_patch:
        patch_exercise_record("access-token", google_id, data_point)

    request_patch.assert_called_once_with(
        f"https://health.googleapis.com/v4/{google_id}",
        headers={
            "Authorization": "Bearer access-token",
            "Content-Type": "application/json",
        },
        json={**data_point, "name": google_id},
        timeout=30,
    )
