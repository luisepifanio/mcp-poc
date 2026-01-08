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
    response = http_client.get("/ping")
    assert response.status_code == 200
    assert response.json() == "pong"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Endpoint not implemented yet")
async def test_get_nonexistent_course(http_client: TestClient) -> None:
    response = http_client.get("/ping")
    assert response.status_code == 200
    assert response.json() == "pong"
