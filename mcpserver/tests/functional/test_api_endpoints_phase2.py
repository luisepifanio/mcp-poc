from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_hello_default(client) -> None:
    response = await client.get("/hello")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "message" in data
    assert data["message"] == "Hello stranger KUN!"


@pytest.mark.asyncio
async def test_hello_with_name(client) -> None:
    response = await client.get("/hello", params={"name": "Luis"})
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Hello Luis KUN!"


@pytest.mark.asyncio
async def test_add_integers(client) -> None:
    response = await client.get("/add/7/5")
    assert response.status_code == 200
    # FastAPI returns a JSON-encoded primitive for simple return types
    assert response.json() == 12


@pytest.mark.asyncio
async def test_cordoba_jokes_returns_nonempty_string(client) -> None:
    response = await client.get("/cordoba_jokes")
    assert response.status_code == 200
    joke = response.json()
    assert isinstance(joke, str)
    assert len(joke) > 0


def test_lifespan_startup_connects_broker_and_does_not_run_faststream_in_test_env() -> (
    None
):
    # Patch connect, setup_database_models and asyncio.create_task before app startup
    with (
        patch(
            "app.infrastructure.api.main.redis_broker.connect", new_callable=AsyncMock
        ) as mock_connect,
        patch(
            "app.infrastructure.api.main.redis_broker._connection",
            None,
        ),
        patch(
            "app.infrastructure.db.connection.setup_database_models",
            new_callable=AsyncMock,
        ) as mock_setup_models,
        patch("asyncio.create_task") as mock_create_task,
        patch(
            "app.infrastructure.api.main.faststream_app.run", new_callable=AsyncMock
        ) as mock_faststream_run,
    ):
        # Import app inside patch context to ensure patched functions are used during lifespan
        from app.infrastructure.api.main import app

        # Trigger startup by creating a TestClient context
        with TestClient(app) as client_sync:
            # Perform a simple request to ensure the app is responsive
            resp = client_sync.get("/hello")
            assert resp.status_code == 200

        # Assertions:
        # Broker should be connected during startup
        mock_connect.assert_awaited()

        # Database models setup should be awaited
        mock_setup_models.assert_awaited()

        # In test environment, faststream should NOT be scheduled to run
        mock_create_task.assert_not_called()
        # And even if called directly, ensure run wasn't awaited (belt-and-suspenders)
        mock_faststream_run.assert_not_awaited()
