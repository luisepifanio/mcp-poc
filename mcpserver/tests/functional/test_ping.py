from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from faststream.redis import RedisBroker
from httpx import ASGITransport, AsyncClient

from app.infrastructure.api.pingrouter import PingRouter


@pytest.mark.asyncio
async def test_async_ping() -> None:
    # 1. Mock de RedisBroker
    mock_redis_broker = AsyncMock(spec=RedisBroker)
    mock_redis_broker._connection = None
    mock_redis_broker.connect = AsyncMock(return_value=None)
    mock_redis_broker.publish = AsyncMock(return_value=None)

    # 2. Mock de _basic_publish para evitar que faststream use Redis real
    with patch.object(
        RedisBroker, "_basic_publish", new_callable=AsyncMock
    ) as mock_basic_publish:
        mock_basic_publish.return_value = None

        # 3. Instanciar PingRouter con el mock
        router = PingRouter(mock_redis_broker)

        # 4. Configurar la aplicación FastAPI con el router mock
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router.router)

        # 5. Usar AsyncClient para hacer la petición
        async with AsyncClient(
            transport=ASGITransport(
                app=app,
                # client=(host, port)
            ),
            base_url="http://test",
        ) as client:
            response = await client.get("/ping")

        # 6. Validaciones
        assert response.status_code == 200
        assert response.text == '"pong"'
        mock_redis_broker.connect.assert_awaited_once()
        mock_redis_broker.publish.assert_awaited_once_with(
            {"message": "Hi there from /ping endpoint"}, stream="in-subject"
        )


@pytest.mark.asyncio
async def test_async_existing_connection_ping() -> None:
    # 1. Mock de RedisBroker
    mock_redis_broker = AsyncMock(spec=RedisBroker)
    # Simular que SI está conectado
    mock_connection = MagicMock()
    mock_connection.connection = "fake_connection"
    mock_redis_broker._connection = mock_connection

    mock_redis_broker.connect = AsyncMock(return_value=None)
    mock_redis_broker.publish = AsyncMock(return_value=None)

    # 2. Mock de _basic_publish para evitar que faststream use Redis real
    with patch.object(
        RedisBroker, "_basic_publish", new_callable=AsyncMock
    ) as mock_basic_publish:
        mock_basic_publish.return_value = None

        # 3. Instanciar PingRouter con el mock
        router = PingRouter(mock_redis_broker)

        # 4. Configurar la aplicación FastAPI con el router mock
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router.router)

        # 5. Usar AsyncClient instanciado en este contexto para evitar problemas de loop
        async with AsyncClient(
            transport=ASGITransport(
                app=app,
                # client=(host, port)
            ),
            base_url="http://test",
        ) as client:
            response = await client.get("/ping")

        # 6. Validaciones
        assert response.status_code == 200
        assert response.text == '"pong"'
        mock_redis_broker.connect.assert_not_awaited()
        mock_redis_broker.publish.assert_awaited_once_with(
            {"message": "Hi there from /ping endpoint"}, stream="in-subject"
        )
