"""Functional tests for PingRouter endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.api.main import create_app


@pytest.fixture
def app_client() -> TestClient:
    """Create FastAPI app and return test client."""
    app = create_app()
    return TestClient(app)


class TestPingEndpoint:
    """Functional tests for /ping endpoint."""

    def test_ping_returns_200(self, app_client: TestClient) -> None:
        """Test that /ping endpoint returns 200 status."""
        response = app_client.get("/ping")
        assert response.status_code == 200

    def test_ping_returns_pong_string(self, app_client: TestClient) -> None:
        """Test that /ping returns 'pong' as response."""
        response = app_client.get("/ping")
        assert response.json() == "pong"

    def test_ping_endpoint_exists(self, app_client: TestClient) -> None:
        """Test that /ping endpoint is registered."""
        response = app_client.get("/ping")
        assert response.status_code == 200

    def test_ping_post_accepts_data(self, app_client: TestClient) -> None:
        """Test that /ping POST accepts data for Redis testing."""
        response = app_client.post("/ping", json={"test": "data"})
        assert response.status_code == 200
        assert response.json()["message"] == "Item received"
        assert response.json()["data"] == {"test": "data"}


class TestAppLifespan:
    """Functional tests for app lifespan and setup."""

    def test_app_creates_successfully(self) -> None:
        """Test that app can be created without errors."""
        app = create_app()
        assert app is not None

    def test_app_has_routers_registered(self, app_client: TestClient) -> None:
        """Test that app has routers registered."""
        # If routers are registered, ping endpoint should exist
        response = app_client.get("/ping")
        assert response.status_code == 200
