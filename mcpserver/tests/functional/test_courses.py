import logging

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_validate_injection(value_inject: str):
    logger.warning("Testing dependency injection...")
    assert value_inject == "injected_value"


@pytest.mark.asyncio
async def test_sync_ping(http_client: TestClient):
    response = http_client.get("/ping")
    assert response.status_code == 200
    assert response.json() == "pong"


@pytest.mark.asyncio
async def test_async_ping(client: AsyncClient):
    response = await client.get("/ping")
    assert response.status_code == 200
    assert response.json() == "pong"


@pytest.mark.ignore
@pytest.mark.asyncio
async def test_get_nonexistent_course(http_client: TestClient):
    response = http_client.get("/courses?courses=67902&courses=65192&force_scrap=false")
    assert response.status_code == 200
    assert response.json() == []
