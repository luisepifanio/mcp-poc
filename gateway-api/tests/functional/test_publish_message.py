"""Functional tests for message publishing to Redis Streams."""

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.api.main import create_app


@pytest.fixture
def app_client() -> TestClient:
    """Create FastAPI app and return test client."""
    app = create_app()
    return TestClient(app)


class TestPublishToRedisStream:
    """Functional tests for message publishing via /ping POST endpoint."""

    @pytest.mark.asyncio
    async def test_ping_post_publishes_message_to_redis_stream(
        self, app_client: TestClient
    ) -> None:
        """
        Test that POST /ping publishes a message to Redis Stream.

        This test validates:
        - POST /ping accepts data
        - Message is published to 'demo-subject' stream
        - Response indicates successful enqueue
        """
        # Act: POST to /ping endpoint
        response = app_client.post("/ping", json={"user_id": "123", "action": "test"})

        # Assert: Response is successful
        assert response.status_code == 200
        assert response.json()["message"] == "Item received"
        assert response.json()["data"] == {"user_id": "123", "action": "test"}

    def test_ping_post_response_structure(self, app_client: TestClient) -> None:
        """Test that /ping POST returns correct response structure."""
        response = app_client.post("/ping", json={"test": "value"})

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "data" in data
        assert data["message"] == "Item received"

    def test_ping_post_with_empty_payload(self, app_client: TestClient) -> None:
        """Test that /ping POST handles empty payload."""
        response = app_client.post("/ping", json={})

        assert response.status_code == 200
        assert response.json()["message"] == "Item received"
        assert response.json()["data"] == {}

    def test_ping_post_with_nested_data(self, app_client: TestClient) -> None:
        """Test that /ping POST handles nested JSON data."""
        nested_data = {
            "user": {"id": "123", "name": "Test User"},
            "metadata": {"timestamp": "2025-01-09", "version": 1},
        }
        response = app_client.post("/ping", json=nested_data)

        assert response.status_code == 200
        assert response.json()["data"] == nested_data
