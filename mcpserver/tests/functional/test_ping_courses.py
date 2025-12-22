import logging
from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from faststream.redis import RedisBroker
from httpx import AsyncClient
from pytest_mock import MockerFixture

from app.infrastructure.api.base_router import BaseRouter
from app.infrastructure.api.pingrouter import PingRouter

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
    response = http_client.get("/courses?courses=67902&courses=65192&force_scrap=false")
    assert response.status_code == 200
    assert response.json() == []
