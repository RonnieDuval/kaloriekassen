"""Mappers to convert Intervals.icu workout data to Google Health API format."""
import datetime as dt
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# Mapping of Intervals.icu activity types to Google Health Exercise types
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


def map_exercise_type(intervals_type: Optional[str]) -> str:
    """
    Map Intervals.icu exercise type to Google Health API exerciseType enum.

    Args:
        intervals_type: Activity type from Intervals.icu (e.g., "VirtualRide")

    Returns:
        Google Health API exerciseType enum value (e.g., "BIKING")
    """
    if not intervals_type:
        return "WORKOUT"  # Default fallback
    
    mapped = EXERCISE_TYPE_MAP.get(intervals_type, "WORKOUT")
    if mapped == "WORKOUT" and intervals_type != "WORKOUT":
        logger.warning(f"Unknown exercise type '{intervals_type}', defaulting to WORKOUT")
    
    return mapped


def calculate_utc_offset(date: dt.date, utc_offset_seconds: int = 7200) -> str:
    """
    Calculate UTC offset duration string.
    
    Args:
        date: Date of the activity
        utc_offset_seconds: UTC offset in seconds (default +02:00 = 7200s for CET)
    
    Returns:
        Duration string for UTC offset (e.g., "7200s")
    """
    return f"{utc_offset_seconds}s"


def map_single_activity_to_google_exercise(
    act: Dict[str, Any],
    utc_offset_seconds: int = 7200
) -> Dict[str, Any]:
    """
    Convert a single raw Intervals.icu activity to Google Health API Exercise DataPoint format.

    Args:
        act: Raw activity dictionary from Intervals.icu
        utc_offset_seconds: UTC offset in seconds

    Returns:
        Dictionary in Google Health API Exercise DataPoint format:
        {
            "clientAssignedId": "...",
            "exercise": {
                "interval": {...},
                "exerciseType": "BIKING",
                "metricsSummary": {...},
                "displayName": "..."
            },
            "dataSource": {...}
        }
    """
    start_date_str = act.get("start_date_local")
    if start_date_str:
        # Standard ISO format: e.g. "2026-05-20T17:34:00"
        start_datetime = dt.datetime.fromisoformat(start_date_str[:19])
        date = start_datetime.date()
    else:
        # Fallback if start_date_local is missing
        date_val = act.get("date")
        if isinstance(date_val, str):
            date = dt.date.fromisoformat(date_val)
        elif isinstance(date_val, dt.date):
            date = date_val
        else:
            date = dt.date.today()
        start_datetime = dt.datetime.combine(date, dt.time(0, 0, 0))

    elapsed_time = act.get("elapsed_time", 0) or 0
    if elapsed_time > 0:
        end_datetime = start_datetime + dt.timedelta(seconds=elapsed_time)
    else:
        end_datetime = start_datetime + dt.timedelta(seconds=1)

    # Convert to ISO format with UTC offset
    utc_offset_hours = utc_offset_seconds // 3600
    utc_offset_minutes = (utc_offset_seconds % 3600) // 60
    offset_str = f"+{utc_offset_hours:02d}:{utc_offset_minutes:02d}"

    start_time = f"{start_datetime.isoformat()}{offset_str}"
    end_time = f"{end_datetime.isoformat()}{offset_str}"

    calories_out = act.get("calories", 0) or 0
    
    # Intervals provides distance in meters in raw activity (or None)
    distance_meters = float(act.get("distance", 0.0) or 0.0)
    distance_km = distance_meters / 1000.0
    distance_millimeters = int(distance_meters * 1000)

    elevation_gain = int(act.get("total_elevation_gain", 0) or 0)
    elevation_millimeters = elevation_gain * 1000

    workout_type = act.get("type")
    exercise_type = map_exercise_type(workout_type)
    display_name = f"{exercise_type}: {distance_km:.1f}km" if distance_km > 0 else exercise_type

    # Build Google Health API DataPoint structure
    data_point = {
        "exercise": {
            "interval": {
                "startTime": start_time,
                "startUtcOffset": calculate_utc_offset(date, utc_offset_seconds),
                "endTime": end_time,
                "endUtcOffset": calculate_utc_offset(date, utc_offset_seconds),
            },
            "exerciseType": exercise_type,
            "metricsSummary": {
                "caloriesKcal": float(calories_out),
            },
            "displayName": display_name,
        },
        "dataSource": {
            "application": {
                "packageName": "com.intervals.icu"
            },
            "recordingMethod": "ACTIVELY_MEASURED",
        }
    }

    # Add optional metrics only if non-zero
    if distance_millimeters > 0:
        data_point["exercise"]["metricsSummary"]["distanceMillimeters"] = distance_millimeters

    if elevation_millimeters > 0:
        data_point["exercise"]["metricsSummary"]["elevationGainMillimeters"] = elevation_millimeters

    if elapsed_time > 0:
        data_point["exercise"]["activeDuration"] = f"{elapsed_time}s"

    return data_point


def map_intervals_to_google_exercise(
    intervals_row: Dict[str, Any],
    utc_offset_seconds: int = 7200
) -> Dict[str, Any]:
    """
    Convert a legacy single Intervals.icu row to Google Health API Exercise DataPoint format.
    Used as fallback when activities list is missing.

    Args:
        intervals_row: Row from raw_intervals table with keys:
            - date: dt.date
            - calories_out: int (kilocalories)
            - distance_km: float (kilometers)
            - elevation_gain: int (meters)
            - workout_type: str (e.g., "VirtualRide") or None
            - elapsed_time: int (seconds) or None
        utc_offset_seconds: UTC offset in seconds (default +02:00 = 7200s for CET)

    Returns:
        Dictionary in Google Health API Exercise DataPoint format
    """
    date = intervals_row["date"]
    calories_out = intervals_row.get("calories_out", 0) or 0
    distance_km = intervals_row.get("distance_km", 0.0) or 0.0
    elevation_gain = intervals_row.get("elevation_gain", 0) or 0
    workout_type = intervals_row.get("workout_type")
    elapsed_time = intervals_row.get("elapsed_time", 0) or 0

    # Calculate start and end times based on elapsed_time to avoid whole-day workouts
    start_datetime = dt.datetime.combine(date, dt.time(0, 0, 0))
    if elapsed_time > 0:
        end_datetime = start_datetime + dt.timedelta(seconds=elapsed_time)
    else:
        end_datetime = start_datetime + dt.timedelta(seconds=1)

    # Convert to ISO format with UTC offset
    utc_offset_hours = utc_offset_seconds // 3600
    utc_offset_minutes = (utc_offset_seconds % 3600) // 60
    offset_str = f"+{utc_offset_hours:02d}:{utc_offset_minutes:02d}"

    start_time = f"{start_datetime.isoformat()}{offset_str}"
    end_time = f"{end_datetime.isoformat()}{offset_str}"

    # Convert distances and elevation to millimeters
    distance_millimeters = int(distance_km * 1_000_000)  # km → mm
    elevation_millimeters = int(elevation_gain * 1_000)  # m → mm

    exercise_type = map_exercise_type(workout_type)
    display_name = f"{exercise_type}: {distance_km:.1f}km" if distance_km > 0 else exercise_type

    # Build Google Health API DataPoint structure
    data_point = {
        "exercise": {
            "interval": {
                "startTime": start_time,
                "startUtcOffset": calculate_utc_offset(date, utc_offset_seconds),
                "endTime": end_time,
                "endUtcOffset": calculate_utc_offset(date, utc_offset_seconds),
            },
            "exerciseType": exercise_type,
            "metricsSummary": {
                "caloriesKcal": float(calories_out),
            },
            "displayName": display_name,
        },
        "dataSource": {
            "application": {
                "packageName": "com.intervals.icu"
            },
            "recordingMethod": "ACTIVELY_MEASURED",
        }
    }

    # Add optional metrics only if non-zero
    if distance_millimeters > 0:
        data_point["exercise"]["metricsSummary"]["distanceMillimeters"] = distance_millimeters

    if elevation_millimeters > 0:
        data_point["exercise"]["metricsSummary"]["elevationGainMillimeters"] = elevation_millimeters

    if elapsed_time > 0:
        data_point["exercise"]["activeDuration"] = f"{elapsed_time}s"

    logger.debug(
        f"Mapped legacy exercise: {date} {exercise_type} "
        f"({calories_out}kcal, {distance_km}km, {elevation_gain}m)"
    )

    return data_point


def map_intervals_batch(
    intervals_rows: list[Dict[str, Any]],
    utc_offset_seconds: int = 7200
) -> list[Dict[str, Any]]:
    """
    Convert multiple Intervals.icu rows to Google Health API Exercise format.

    Args:
        intervals_rows: List of rows from raw_intervals
        utc_offset_seconds: UTC offset in seconds

    Returns:
        List of Google Health API DataPoint dictionaries
    """
    import json
    mapped_data_points = []
    
    for row in intervals_rows:
        activities = row.get("activities")
        parsed_activities = []
        
        if activities:
            if isinstance(activities, str):
                try:
                    parsed_activities = json.loads(activities)
                except Exception as e:
                    logger.warning(f"Failed to parse activities JSON on {row.get('date')}: {e}")
            elif isinstance(activities, list):
                parsed_activities = activities
        
        if parsed_activities:
            # Map each individual activity
            for act in parsed_activities:
                if act.get("type"):
                    mapped_data_points.append(
                        map_single_activity_to_google_exercise(act, utc_offset_seconds)
                    )
        elif row.get("workout_type"):
            # Fallback to the daily aggregated row (backwards compatibility)
            mapped_data_points.append(
                map_intervals_to_google_exercise(row, utc_offset_seconds)
            )
            
    return mapped_data_points
