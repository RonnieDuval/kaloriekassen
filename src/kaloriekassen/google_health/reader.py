"""Read-only Google Health API client."""
from datetime import date
from typing import Any
import requests

from .client import GOOGLE_HEALTH_EXERCISE_ENDPOINT

GOOGLE_HEALTH_NUTRITION_LOG_ENDPOINT = (
    "https://health.googleapis.com/v4/users/me/dataTypes/nutrition-log/dataPoints"
)
GOOGLE_HEALTH_DATA_POINT_ENDPOINT = (
    "https://health.googleapis.com/v4/users/me/dataTypes/{data_type}/dataPoints"
)


def _civil_date_time(value: date) -> dict[str, Any]:
    return {
        "date": {"year": value.year, "month": value.month, "day": value.day},
        "time": {},
    }


def fetch_daily_rollups(
    access_token: str,
    data_type: str,
    start_date: date,
    end_date: date,
    page_size: int = 14,
) -> list[dict[str, Any]]:
    """Return daily rollups for a closed-open civil date range.

    Google limits some energy rollups to 14 days. Callers are responsible for
    splitting larger ranges before calling this low-level reader.
    """
    if end_date <= start_date:
        raise ValueError("end_date must be after start_date")

    endpoint = GOOGLE_HEALTH_DATA_POINT_ENDPOINT.format(data_type=data_type)
    endpoint = f"{endpoint}:dailyRollUp"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    request_body: dict[str, Any] = {
        "range": {
            "start": _civil_date_time(start_date),
            "end": _civil_date_time(end_date),
        },
        "windowSizeDays": 1,
        "pageSize": page_size,
    }
    records: list[dict[str, Any]] = []

    while True:
        response = requests.post(
            endpoint,
            headers=headers,
            json=request_body,
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            try:
                google_error = response.json().get("error", {})
            except ValueError:
                google_error = {}
            reason = google_error.get("message")
            details = google_error.get("details")
            suffix = f" Google Health: {reason}. Details: {details}" if reason else ""
            raise requests.HTTPError(
                f"{error}.{suffix}",
                response=response,
            ) from error
        payload = response.json()
        records.extend(payload.get("rollupDataPoints", []))

        page_token = payload.get("nextPageToken")
        if not page_token:
            return records
        request_body["pageToken"] = page_token


def fetch_exercises(
    access_token: str,
    page_size: int = 25,
    filter_expression: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch all exercise records from Google Health without changing them."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    page_token: str | None = None
    records: list[dict[str, Any]] = []

    while True:
        params: dict[str, Any] = {"pageSize": page_size}
        if filter_expression:
            params["filter"] = filter_expression
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(
            GOOGLE_HEALTH_EXERCISE_ENDPOINT,
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
