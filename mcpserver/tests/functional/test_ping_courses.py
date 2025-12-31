import logging

import pytest
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_validate_injection(value_inject: str) -> None:
    logger.warning("Testing dependency injection...")
    assert value_inject == "injected_value"


@pytest.mark.asyncio
async def test_sync_ping(http_client: TestClient) -> None:
    # Patch FastStream publisher to avoid hitting real Redis serialization
    from unittest.mock import AsyncMock, patch

    from faststream.redis import RedisBroker

    with (
        patch.object(
            RedisBroker, "_basic_publish", new_callable=AsyncMock
        ) as mock_basic_publish,
        patch.object(RedisBroker, "publish", new_callable=AsyncMock) as mock_publish,
    ):
        mock_basic_publish.return_value = None
        mock_publish.return_value = None
        response = http_client.get("/ping")
    assert response.status_code == 200
    assert response.json() == "pong"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Endpoint not implemented yet")
async def test_get_nonexistent_course(http_client: TestClient) -> None:
    response = http_client.get("/courses?courses=67902&courses=65192&force_scrap=false")
    assert response.status_code == 200
    assert response.json() == []
