from kaloriekassen import db as connection


def test_database_type_defaults_to_sqlite_outside_a_container(monkeypatch):
    monkeypatch.delenv("DB_TYPE", raising=False)
    monkeypatch.setattr(connection, "is_running_in_container", lambda: False)
    assert connection.get_db_type() == "sqlite"


def test_database_type_defaults_to_postgres_in_a_container(monkeypatch):
    monkeypatch.delenv("DB_TYPE", raising=False)
    monkeypatch.setattr(connection, "is_running_in_container", lambda: True)
    assert connection.get_db_type() == "postgres"


def test_database_type_can_be_overridden(monkeypatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setattr(connection, "is_running_in_container", lambda: True)
    assert connection.get_db_type() == "sqlite"


def test_postgres_schema_uses_supported_view_creation_syntax():
    assert "CREATE VIEW IF NOT EXISTS" not in connection.POSTGRES_SCHEMA
    assert "CREATE OR REPLACE VIEW nutrition_meal_totals" in connection.POSTGRES_SCHEMA
    assert "CREATE OR REPLACE VIEW daily_nutrition" in connection.POSTGRES_SCHEMA
