"""Live tests for inspecting Google Health nutrition log responses."""
from datetime import date, timedelta
import json

import pytest

from kaloriekassen.integrations.google_health.auth import get_credentials
from kaloriekassen.integrations.google_health.reader import fetch_nutrition_logs


@pytest.mark.integration
def test_fetch_recent_nutrition_logs_from_google_health():
    """Fetch and print the raw nutritionLog payload returned by Google Health."""
    end_date = date.today() + timedelta(days=1)
    start_date = end_date - timedelta(days=8)
    filter_expression = (
        f'nutrition_log.interval.civil_start_time >= "{start_date.isoformat()}" AND '
        f'nutrition_log.interval.civil_start_time < "{end_date.isoformat()}"'
    )

    records = fetch_nutrition_logs(
        get_credentials().token,
        filter_expression=filter_expression,
    )

    print(json.dumps({"dataPoints": records}, indent=2, ensure_ascii=False))
    assert isinstance(records, list)
    assert all("nutritionLog" in record for record in records)
