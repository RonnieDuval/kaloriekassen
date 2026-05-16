import importlib.util
from pathlib import Path

import pytest


def load_hent_intervals_module():
    module_path = Path(__file__).resolve().parents[1] / "INTERVALS_ICU" / "hent_intervals_icu.py"
    spec = importlib.util.spec_from_file_location("hent_intervals_icu", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
def test_fetch_intervals_activities_live():
    module = load_hent_intervals_module()

    athlete_id = getattr(module.settings, "INTERVALS_ATHLETE_ID", None)
    api_key = getattr(module.settings, "INTERVALS_API_KEY", None)
    if not athlete_id or not api_key:
        pytest.skip("INTERVALS_ATHLETE_ID/INTERVALS_API_KEY not configured")
    if module.pd is None:
        pytest.skip("pandas is not installed")

    df = module.fetch_intervals_activities()

    assert hasattr(df, "shape")
    assert len(df.columns) > 0


def test_fetch_intervals_activities_requires_credentials():
    module = load_hent_intervals_module()

    with pytest.raises(ValueError, match="INTERVALS_ATHLETE_ID and INTERVALS_API_KEY must be set"):
        module.fetch_intervals_activities(athlete_id="", api_key="")
