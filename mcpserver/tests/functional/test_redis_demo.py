import logging
from typing import Any

import pytest
from faststream.redis import TestApp, TestRedisBroker

from app.infrastructure.redis.main import (
    app,
    broker,
)
from app.infrastructure.redis.main import (
    handle_incoming_enqueue_event as handle_message,
)

logger = logging.getLogger(__name__)


@pytest.mark.redis()
@pytest.mark.asyncio()
async def test_redis_communication() -> None:
    """Tests the full message flow using the in-memory TestRedisBroker."""

    # Use TestApp and TestRedisBroker as context managers
    async with TestRedisBroker(broker) as test_broker, TestApp(app) as test_app:
        # The broker here is an in-memory patched version
        # test_broker: TestRedisBroker = test_app.broker # type: ignore

        message: dict[str, Any] = {"data": "Test message"}

        # Publish a message to the input channel
        await test_broker.publish(message, stream="in-subject")

        logger.info(f"handle_message.mock: {handle_message.mock}")

        # You can check if the handler was called and what it returned
        handle_message.mock.assert_called_once_with(message)
        handle_message.mock.assert_called_once()
