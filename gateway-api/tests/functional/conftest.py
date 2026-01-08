from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient as FastApiTestClient
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True, scope="function")
def value_inject() -> str:
    return "injected_value"


@pytest.fixture(autouse=True, scope="function")
def http_client() -> FastApiTestClient:
    from app.infrastructure.api.main import app

    # Or you can configure the app here before returning the client

    return FastApiTestClient(app)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # host, port = "127.0.0.1", "9000"
    from app.infrastructure.api.main import app

    async with AsyncClient(
        transport=ASGITransport(
            app=app,
            # client=(host, port)
        ),
        base_url="http://test",
    ) as client:
        yield client
