"""Read-only Google Health API client."""
from typing import Any
import requests

from .client import GOOGLE_HEALTH_EXERCISE_ENDPOINT

GOOGLE_HEALTH_NUTRITION_LOG_ENDPOINT = (
    "https://health.googleapis.com/v4/users/me/dataTypes/nutrition-log/dataPoints"
)


def fetch_exercises(access_token: str, page_size: int = 100) -> list[dict[str, Any]]:
    """Fetch exercise records from Google Health without changing remote data."""
    response = requests.get(
        GOOGLE_HEALTH_EXERCISE_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        params={"pageSize": page_size}, timeout=30,
    )
    response.raise_for_status()
    return response.json().get("dataPoints", [])


def fetch_nutrition_logs(
    access_token: str,
    page_size: int = 100,
    filter_expression: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch all matching Google Health nutrition logs without changing them.

    ``filter_expression`` is passed directly to the Google Health API. For
    example, logs for a civil date range can be selected with::

        nutrition_log.interval.civil_start_time >= "2026-07-20" AND
        nutrition_log.interval.civil_start_time < "2026-07-21"
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    params: dict[str, Any] = {"pageSize": page_size}
    if filter_expression:
        params["filter"] = filter_expression

    records: list[dict[str, Any]] = []
    while True:
        response = requests.get(
            GOOGLE_HEALTH_NUTRITION_LOG_ENDPOINT,
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        records.extend(payload.get("dataPoints", []))

        page_token = payload.get("nextPageToken")
        if not page_token:
            return records
        params["pageToken"] = page_token
