"""Map Intervals.icu activities to Google Health exercise records."""
import datetime as dt
import logging
import os
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Europe/Copenhagen"
DEFAULT_TIMEZONE_ENV_VAR = "GOOGLE_HEALTH_DEFAULT_TIMEZONE"

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


def _timezone_for_activity(activity: dict[str, Any]) -> ZoneInfo:
    """Return the activity timezone or the configured IANA fallback timezone."""
    timezone_name = str(activity.get("timezone") or "").strip()
    if not timezone_name:
        timezone_name = os.getenv(
            DEFAULT_TIMEZONE_ENV_VAR,
            DEFAULT_TIMEZONE,
        ).strip() or DEFAULT_TIMEZONE
        logger.warning(
            "Activity %r has no timezone; using fallback %s.",
            activity.get("id") or activity.get("activity_id") or activity.get("start_date"),
            timezone_name,
        )

    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Unknown IANA timezone: {timezone_name!r}") from error


def _activity_start(activity: dict[str, Any], timezone: ZoneInfo) -> dt.datetime:
    """Return an aware local start time, preferring the absolute UTC timestamp."""
    absolute_start = activity.get("start_date")
    if absolute_start:
        start = dt.datetime.fromisoformat(str(absolute_start).replace("Z", "+00:00"))
        if start.tzinfo is None:
            logger.warning("Activity start_date %r has no UTC offset; assuming UTC.", absolute_start)
            start = start.replace(tzinfo=dt.timezone.utc)
        return start.astimezone(timezone)

    local_start = activity.get("start_date_local")
    if local_start:
        logger.warning(
            "Activity %r has no absolute start_date; interpreting start_date_local in %s.",
            activity.get("id") or activity.get("activity_id") or local_start,
            timezone.key,
        )
        start = dt.datetime.fromisoformat(str(local_start))
        return start.astimezone(timezone) if start.tzinfo else start.replace(tzinfo=timezone)

    date_value = activity.get("date")
    if isinstance(date_value, str):
        date = dt.date.fromisoformat(date_value)
    elif isinstance(date_value, dt.date):
        date = date_value
    else:
        date = dt.date.today()
    logger.warning("Activity has no start time; using midnight on %s in %s.", date, timezone.key)
    return dt.datetime.combine(date, dt.time(), tzinfo=timezone)


def map_single_activity_to_google_exercise(activity: dict[str, Any]) -> dict[str, Any]:
    """Convert one raw Intervals.icu activity to a Google Health data point."""
    timezone = _timezone_for_activity(activity)
    start = _activity_start(activity, timezone)
    elapsed_seconds = int(activity.get("elapsed_time", 0) or 0)
    end = (
        start.astimezone(dt.timezone.utc)
        + dt.timedelta(seconds=max(elapsed_seconds, 1))
    ).astimezone(timezone)
    start_offset = int(start.utcoffset().total_seconds())
    end_offset = int(end.utcoffset().total_seconds())

    distance_meters = float(activity.get("distance", 0) or 0)
    elevation_meters = float(activity.get("total_elevation_gain", 0) or 0)
    exercise_type = map_exercise_type(activity.get("type"))
    distance_km = distance_meters / 1000
    display_name = (
        f"{exercise_type}: {distance_km:.1f}km" if distance_meters else exercise_type
    )

    exercise: dict[str, Any] = {
        "interval": {
            "startTime": start.isoformat(),
            "startUtcOffset": f"{start_offset}s",
            "endTime": end.isoformat(),
            "endUtcOffset": f"{end_offset}s",
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
