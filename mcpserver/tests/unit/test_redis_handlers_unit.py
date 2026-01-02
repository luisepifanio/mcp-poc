from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_startup_connects_when_not_connected() -> None:
    # Import function and broker, then patch broker.connect and set disconnected state
    from app.infrastructure.redis.main import broker, startup

    broker._connection = None
    with patch.object(broker, "connect", new_callable=AsyncMock) as mock_connect:
        context = MagicMock()
        await startup(context)

        mock_connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_skips_connect_when_already_connected() -> None:
    from app.infrastructure.redis.main import broker, startup

    conn = MagicMock()
    conn.connection = "fake"
    broker._connection = conn

    with patch.object(broker, "connect", new_callable=AsyncMock) as mock_connect:
        context = MagicMock()
        await startup(context)

        mock_connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscriber_demo_ack_on_success() -> None:
    from app.infrastructure.redis.main import subscriber_demo

    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()

    body = {"message": "Hi there from /ping endpoint"}

    await subscriber_demo(body, msg)

    msg.ack.assert_awaited_once()
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscriber_demo_ack_on_exception() -> None:
    from app.infrastructure.redis.main import subscriber_demo

    msg = MagicMock()
    # Force ack to raise to hit exception path
    msg.ack = AsyncMock(side_effect=Exception("boom"))
    msg.nack = AsyncMock()

    body = {"message": "Hi there"}

    await subscriber_demo(body, msg)

    msg.nack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_processing_event_queue_ack_and_return_processed() -> None:
    from app.infrastructure.redis.main import handle_processing_event_queue

    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()

    body = {"data": 123}
    result = await handle_processing_event_queue(body, msg)

    msg.ack.assert_awaited_once()
    msg.nack.assert_not_awaited()
    assert isinstance(result, dict)
    assert result == {"processed_data": body}


@pytest.mark.asyncio
async def test_handle_processing_event_queue_nack_on_exception() -> None:
    from app.infrastructure.redis.main import handle_processing_event_queue

    msg = MagicMock()
    msg.ack = AsyncMock(side_effect=Exception("fail"))
    msg.nack = AsyncMock()

    body = {"data": "x"}
    result = await handle_processing_event_queue(body, msg)

    msg.nack.assert_awaited_once()
    assert result is None
