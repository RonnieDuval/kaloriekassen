import json
import pytest

from kaloriekassen.db import get_db_connection
from kaloriekassen.withings.sync import ingest_measure_payload
from kaloriekassen.withings.transform import transform_measure_groups


def _payload():
    return {
        "status": 0,
        "body": {
            "measuregrps": [
                {
                    "grpid": 12345,
                    "date": 1723611600,
                    "model": "Body Comp",
                    "measures": [
                        {"value": 80345, "type": 1, "unit": -3},
                        {"value": 187, "type": 6, "unit": -1},
                        {"value": 15025, "type": 8, "unit": -3},
                        {"value": 65320, "type": 5, "unit": -3},
                        {"value": 999, "type": 999, "unit": 0},
                    ],
                }
            ]
        },
    }


def test_transforms_withings_units_and_supported_measure_types():
    row = transform_measure_groups(_payload())[0]

    assert row["measurement_id"] == "withings:12345"
    assert row["measured_at"] == "2024-08-14T05:00:00+00:00"
    assert row["source"] == "withings"
    assert row["source_id"] == "12345"
    assert row["payload"] == _payload()["body"]["measuregrps"][0]
    assert row["weight_kg"] == pytest.approx(80.345)
    assert row["body_fat_pct"] == pytest.approx(18.7)
    assert row["fat_mass_kg"] == pytest.approx(15.025)
    assert row["fat_free_mass_kg"] == pytest.approx(65.32)


def test_ingests_withings_payload_idempotently(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "withings.db"))

    assert ingest_measure_payload(_payload()) == 1
    assert ingest_measure_payload(_payload()) == 1

    with get_db_connection() as connection:
        row = connection.execute(
            """SELECT measurement_id, weight_kg, body_fat_pct, fat_mass_kg,
                      fat_free_mass_kg, source, source_id, payload
               FROM body_measurements"""
        ).fetchone()

    assert row[0] == "withings:12345"
    assert row[1:5] == pytest.approx((80.345, 18.7, 15.025, 65.32))
    assert row[5:7] == ("withings", "12345")
    assert json.loads(row[7])["model"] == "Body Comp"
