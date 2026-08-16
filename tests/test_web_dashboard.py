from fastapi.testclient import TestClient

from kaloriekassen.db import get_db_connection
from kaloriekassen.web.app import app


def seed_dashboard_database():
    with get_db_connection() as connection:
        connection.execute(
            """INSERT INTO raw_mfp (date, meals_detail)
               VALUES (?, ?)""",
            ("2026-08-14", "[]"),
        )
        connection.execute(
            """INSERT INTO nutrition_entries
               (entry_id, date, meal_type, source_meal_name, position,
                food_name, calories, protein_g, carbs_g, fat_g, sodium_mg,
                sugar_g)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "food-1", "2026-08-14", "breakfast", "Morgenmad", 0,
                "Havregryn", 400.0, 15.0, 55.0, 10.0, 120.0, 4.0,
            ),
        )
        connection.execute(
            """INSERT INTO google_health_daily_activity
               (date, steps, active_energy_kcal, total_energy_kcal, payload)
               VALUES (?, ?, ?, ?, ?)""",
            ("2026-08-14", 6000, 500.0, 2700.0, "{}"),
        )
        connection.execute(
            """INSERT INTO raw_intervals
               (activity_id, started_at, activity_type, calories_out, payload)
               VALUES (?, ?, ?, ?, ?)""",
            ("activity-1", "2026-08-14T08:00:00+00:00", "Ride", 450.0, "{}"),
        )
        connection.execute(
            """INSERT INTO body_measurements
               (measurement_id, measured_at, weight_kg, body_fat_pct,
                source, source_id, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "weight-1", "2026-08-14T06:00:00+00:00", 113.2, 28.5,
                "withings", "weight-1", "{}",
            ),
        )
        connection.execute(
            """INSERT INTO sync_runs
               (run_id, job, source, status, fetched_count, stored_count,
                started_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "run-1", "myfitnesspal", "myfitnesspal", "success", 1, 1,
                "2026-08-14T09:00:00+00:00", "2026-08-14T09:00:01+00:00",
            ),
        )


def test_dashboard_page_and_static_assets_are_served():
    client = TestClient(app)

    response = client.get("/")
    stylesheet = client.get("/static/styles.css")
    script = client.get("/static/dashboard.js")

    assert response.status_code == 200
    assert "Kaloriekassen" in response.text
    assert "Dagens overblik" in response.text
    assert "Grøn betyder, at seneste kørsel lykkedes" in response.text
    assert stylesheet.status_code == 200
    assert "--green" in stylesheet.text
    assert script.status_code == 200
    assert "loadDashboard" in script.text
    assert "Synkronisering OK" in script.text
    assert "opdateres fra Google hvert 15. minut" in script.text
    assert '"google-health-today": ["Hvert 15. minut"' in script.text


def test_dashboard_api_returns_derived_energy_data():
    seed_dashboard_database()
    client = TestClient(app)

    response = client.get("/api/dashboard", params={"days": 30})

    assert response.status_code == 200
    payload = response.json()
    assert payload["daily"] == [
        {
            "date": "2026-08-14",
            "calories_in": 400.0,
            "basal_energy_kcal": 2098.25,
            "steps": 6000,
            "step_energy_estimated_kcal": 260.7279,
            "exercise_energy_kcal": 450.0,
            "active_energy_kcal": 500.0,
            "estimated_tdee_kcal": 2700.0,
            "estimated_energy_balance_kcal": -2300.0,
            "weight_kg": 113.2,
            "body_fat_pct": 28.5,
            "energy_model": "google_total_calories",
            "data_completeness": "complete",
        }
    ]
    assert payload["activities"][0]["activity_id"] == "activity-1"
    assert payload["measurements"][0]["weight_kg"] == 113.2
    assert payload["sync_jobs"][0]["status"] == "success"


def test_day_api_returns_food_and_activity_details():
    seed_dashboard_database()
    client = TestClient(app)

    response = client.get("/api/days/2026-08-14")
    missing = client.get("/api/days/2026-08-13")

    assert response.status_code == 200
    payload = response.json()
    assert payload["nutrition_entries"][0]["food_name"] == "Havregryn"
    assert payload["activities"][0]["activity_type"] == "Ride"
    assert payload["measurement"]["weight_kg"] == 113.2
    assert missing.status_code == 404


def test_health_checks_database_connection():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
