"""HTTP client for Withings body measurements."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

import requests

from kaloriekassen.withings.auth import API_BASE_URL, WithingsApiError, get_access_token


def _unix_start(day: date) -> int:
    return int(datetime.combine(day, time.min, tzinfo=timezone.utc).timestamp())


def fetch_measurements(start: date, end: date) -> dict[str, Any]:
    """Fetch all real measurement groups in an inclusive UTC date range."""
    groups: list[dict[str, Any]] = []
    offset: int | None = None
    access_token = get_access_token()

    while True:
        data: dict[str, Any] = {
            "action": "getmeas",
            "category": 1,
            "startdate": _unix_start(start),
            "enddate": _unix_start(end) + 86400 - 1,
        }
        if offset is not None:
            data["offset"] = offset
        response = requests.post(
            f"{API_BASE_URL}/measure",
            headers={"Authorization": f"Bearer {access_token}"},
            data=data,
            timeout=30,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError as error:
            raise WithingsApiError("Withings returned invalid measurement JSON") from error
        if not isinstance(payload, dict) or payload.get("status") != 0:
            status = payload.get("status") if isinstance(payload, dict) else "unknown"
            raise WithingsApiError(f"Withings measure API returned status {status}")
        body = payload.get("body", {})
        page_groups = body.get("measuregrps", []) if isinstance(body, dict) else []
        if not isinstance(page_groups, list):
            raise WithingsApiError("Withings measure response has invalid measuregrps")
        groups.extend(group for group in page_groups if isinstance(group, dict))
        if not body.get("more"):
            break
        next_offset = body.get("offset")
        if next_offset is None or next_offset == offset:
            raise WithingsApiError("Withings pagination did not provide a new offset")
        offset = int(next_offset)

    return {"status": 0, "body": {"measuregrps": groups}}
