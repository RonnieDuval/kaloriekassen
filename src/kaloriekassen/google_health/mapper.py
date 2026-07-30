"""Map Intervals.icu activities to Google Health exercise records."""
import datetime as dt
import logging
from typing import Any


logger = logging.getLogger(__name__)

EXERCISE_TYPE_MAP = {
    "VirtualRide": "BIKING",
    "Ride": "BIKING",
    "MountainBike": "BIKING",
    "Run": "RUNNING",
    "Trail": "RUNNING",
    "Walk": "WALKING",
    "Hike": "HIKING",
    "Swim": "SWIMMING",
    "Yoga": "YOGA",
    "Strength": "STRENGTH_TRAINING",
    "WeightTraining": "STRENGTH_TRAINING",
    "CrossFit": "WORKOUT",
    "HIIT": "HIIT",
    "Pilates": "PILATES",
}


def map_exercise_type(intervals_type: str | None) -> str:
    """Map an Intervals.icu activity type to a Google Health enum."""
    if not intervals_type:
        return "WORKOUT"
    exercise_type = EXERCISE_TYPE_MAP.get(intervals_type, "WORKOUT")
    if exercise_type == "WORKOUT" and intervals_type != "WORKOUT":
        logger.warning("Unknown exercise type %r; using WORKOUT.", intervals_type)
    return exercise_type


def _offset_strings(utc_offset_seconds: int) -> tuple[str, str]:
    """Return RFC 3339 and protobuf-duration representations of an offset."""
    sign = "+" if utc_offset_seconds >= 0 else "-"
    absolute_seconds = abs(utc_offset_seconds)
    hours, remainder = divmod(absolute_seconds, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}", f"{utc_offset_seconds}s"


def map_single_activity_to_google_exercise(
    activity: dict[str, Any],
    utc_offset_seconds: int = 7200,
) -> dict[str, Any]:
    """Convert one raw Intervals.icu activity to a Google Health data point."""
    start_date = activity.get("start_date_local")
    if start_date:
        start = dt.datetime.fromisoformat(start_date[:19])
    else:
        date_value = activity.get("date")
        if isinstance(date_value, str):
            date = dt.date.fromisoformat(date_value)
        elif isinstance(date_value, dt.date):
            date = date_value
        else:
            date = dt.date.today()
        start = dt.datetime.combine(date, dt.time())

    elapsed_seconds = int(activity.get("elapsed_time", 0) or 0)
    end = start + dt.timedelta(seconds=max(elapsed_seconds, 1))
    rfc3339_offset, duration_offset = _offset_strings(utc_offset_seconds)

    distance_meters = float(activity.get("distance", 0) or 0)
    elevation_meters = float(activity.get("total_elevation_gain", 0) or 0)
    exercise_type = map_exercise_type(activity.get("type"))
    distance_km = distance_meters / 1000
    display_name = (
        f"{exercise_type}: {distance_km:.1f}km" if distance_meters else exercise_type
    )

    exercise: dict[str, Any] = {
        "interval": {
            "startTime": f"{start.isoformat()}{rfc3339_offset}",
            "startUtcOffset": duration_offset,
            "endTime": f"{end.isoformat()}{rfc3339_offset}",
            "endUtcOffset": duration_offset,
        },
        "exerciseType": exercise_type,
        "metricsSummary": {
            "caloriesKcal": float(activity.get("calories", 0) or 0),
        },
        "displayName": display_name,
    }
    if distance_meters:
        exercise["metricsSummary"]["distanceMillimeters"] = int(
            distance_meters * 1000
        )
    if elevation_meters:
        exercise["metricsSummary"]["elevationGainMillimeters"] = int(
            elevation_meters * 1000
        )
    if elapsed_seconds:
        exercise["activeDuration"] = f"{elapsed_seconds}s"

    return {
        "exercise": exercise,
        "dataSource": {
            "application": {"packageName": "com.intervals.icu"},
            "recordingMethod": "ACTIVELY_MEASURED",
        },
    }
