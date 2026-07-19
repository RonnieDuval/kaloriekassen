"""Read-only Google Health replica client."""
from typing import Any
import requests

from .client import GOOGLE_HEALTH_EXERCISE_ENDPOINT


def fetch_exercises(access_token: str, page_size: int = 100) -> list[dict[str, Any]]:
    """Fetch exercise records from Google Health without changing remote data."""
    response = requests.get(
        GOOGLE_HEALTH_EXERCISE_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        params={"pageSize": page_size}, timeout=30,
    )
    response.raise_for_status()
    return response.json().get("dataPoints", [])
