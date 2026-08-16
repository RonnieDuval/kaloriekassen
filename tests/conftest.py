"""Shared test isolation for local database access."""

import pytest


@pytest.fixture(autouse=True)
def isolate_default_sqlite_database(monkeypatch, tmp_path):
    """Prevent tests without an explicit path from opening kaloriekassen.db."""
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "default-test.db"))
    monkeypatch.setenv("OAUTH_UPLOAD_TO_NAS", "false")
