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

    def test_ping_uses_correct_method(self, app_client: TestClient) -> None:
        """Test that /ping only accepts GET requests."""
        response = app_client.post("/ping")
        assert response.status_code == 405  # Method Not Allowed


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
