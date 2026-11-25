"""
Shared test setup (pytest loads this file automatically).

Every test gets its own empty, temporary database file, so tests never
touch the real data/relief.db and never affect each other.
"""

import pytest
from fastapi.testclient import TestClient

from app import config, main as main_module
from app.main import app


@pytest.fixture(autouse=True)
def disable_background_alert_sync(monkeypatch):
    """Keep the test suite offline; feed sync endpoints are mocked in API tests."""
    monkeypatch.setattr(main_module, "ALERT_AUTO_SYNC_ENABLED", False)
    monkeypatch.setenv("LLM_ENABLED", "false")


@pytest.fixture
def temp_database(tmp_path, monkeypatch):
    """Point the app at a fresh database file inside a temporary folder."""
    database_path = tmp_path / "test_relief.db"
    monkeypatch.setattr(config, "DATABASE_PATH", database_path)
    return database_path


@pytest.fixture
def client(temp_database):
    """A test client; using `with` runs the app's startup code (creates tables)."""
    with TestClient(app) as test_client:
        yield test_client

