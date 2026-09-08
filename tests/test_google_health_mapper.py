from kaloriekassen.google_health.mapper import map_single_activity_to_google_exercise


def test_maps_raw_intervals_activity_to_google_exercise():
    result = map_single_activity_to_google_exercise(
        {
            "start_date": "2026-07-20T08:00:00Z",
            "start_date_local": "2026-07-20T10:00:00",
            "timezone": "Europe/Copenhagen",
            "elapsed_time": 3600,
            "type": "Ride",
            "calories": 500,
            "distance": 20_000,
            "total_elevation_gain": 125,
            "average_heartrate": 164.4,
        }
    )

    exercise = result["exercise"]
    assert exercise["interval"] == {
        "startTime": "2026-07-20T10:00:00+02:00",
        "startUtcOffset": "7200s",
        "endTime": "2026-07-20T11:00:00+02:00",
        "endUtcOffset": "7200s",
    }
    assert exercise["exerciseType"] == "BIKING"
    assert exercise["metricsSummary"] == {
        "caloriesKcal": 500.0,
        "distanceMillimeters": 20_000_000,
        "elevationGainMillimeters": 125_000,
        "averageHeartRateBeatsPerMinute": "164",
    }
    assert exercise["activeDuration"] == "3600s"


def test_uses_winter_offset_for_copenhagen():
    result = map_single_activity_to_google_exercise(
        {
            "start_date": "2026-01-20T09:00:00Z",
            "timezone": "Europe/Copenhagen",
            "elapsed_time": 3600,
        }
    )

    assert result["exercise"]["interval"] == {
        "startTime": "2026-01-20T10:00:00+01:00",
        "startUtcOffset": "3600s",
        "endTime": "2026-01-20T11:00:00+01:00",
        "endUtcOffset": "3600s",
    }


def test_handles_daylight_saving_transition_during_activity():
    result = map_single_activity_to_google_exercise(
        {
            "start_date": "2026-03-29T00:30:00Z",
            "timezone": "Europe/Copenhagen",
            "elapsed_time": 7200,
        }
    )

    assert result["exercise"]["interval"] == {
        "startTime": "2026-03-29T01:30:00+01:00",
        "startUtcOffset": "3600s",
        "endTime": "2026-03-29T04:30:00+02:00",
        "endUtcOffset": "7200s",
    }
    assert result["exercise"]["activeDuration"] == "7200s"


def test_uses_activity_timezone_outside_denmark():
    result = map_single_activity_to_google_exercise(
        {
            "start_date": "2026-07-20T14:00:00Z",
            "timezone": "America/New_York",
            "elapsed_time": 1800,
        }
    )

    assert result["exercise"]["interval"] == {
        "startTime": "2026-07-20T10:00:00-04:00",
        "startUtcOffset": "-14400s",
        "endTime": "2026-07-20T10:30:00-04:00",
        "endUtcOffset": "-14400s",
    }


def test_uses_configured_fallback_when_activity_has_no_timezone(monkeypatch, caplog):
    monkeypatch.setenv("GOOGLE_HEALTH_DEFAULT_TIMEZONE", "America/New_York")

    result = map_single_activity_to_google_exercise(
        {
            "id": "activity-1",
            "start_date": "2026-01-20T15:00:00Z",
            "elapsed_time": 3600,
        }
    )

    assert result["exercise"]["interval"]["startTime"] == "2026-01-20T10:00:00-05:00"
    assert "has no timezone; using fallback America/New_York" in caplog.text
