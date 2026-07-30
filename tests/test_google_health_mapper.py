from kaloriekassen.google_health.mapper import map_single_activity_to_google_exercise


def test_maps_raw_intervals_activity_to_google_exercise():
    result = map_single_activity_to_google_exercise(
        {
            "start_date_local": "2026-07-20T10:00:00",
            "elapsed_time": 3600,
            "type": "Ride",
            "calories": 500,
            "distance": 20_000,
            "total_elevation_gain": 125,
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
    }
    assert exercise["activeDuration"] == "3600s"
