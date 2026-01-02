import logging
from typing import Any
from uuid import uuid4

import pytest
from faststream.redis import TestApp, TestRedisBroker

from app.core.usecases.event_usecases import EnqueuedEventUseCaseInput
from app.infrastructure.redis.main import (
    app,
    broker,
    handle_enqueue_event,
    subscriber_demo,
)

logger = logging.getLogger(__name__)


@pytest.mark.asyncio()
async def test_redis_demo_subscriber() -> None:
    """Tests the full message flow using the in-memory TestRedisBroker."""

    # Use TestApp and TestRedisBroker as context managers
    async with TestRedisBroker(broker) as test_broker, TestApp(app):
        # The broker here is an in-memory patched version
        # test_broker: TestRedisBroker = test_app.broker # type: ignore

        message: dict[str, Any] = {"data": "Test message"}

        # Publish a message to the input channel
        await test_broker.publish(message, stream="demo-subject")

        logger.info(f"subscriber_demo.mock: {subscriber_demo.mock}")

        # You can check if the handler was called and what it returned
        subscriber_demo.mock.assert_called_once_with(message)
        subscriber_demo.mock.assert_called_once()


@pytest.mark.asyncio()
async def test_enqueue_event() -> None:
    """Tests enqueeing events using TestRedisBroker."""

    # Use TestApp and TestRedisBroker as context managers
    async with TestRedisBroker(broker) as test_broker:
        # The broker here is an in-memory patched version
        # test_broker: TestRedisBroker = test_app.broker # type: ignore

        message: EnqueuedEventUseCaseInput = EnqueuedEventUseCaseInput(
            name="TrackEvent",
            payload={"key": "value"},
            external_uuid=uuid4(),
            context={"source": "pytest"},
        )

        # Publish a message to the input channel
        await test_broker.publish(message, stream="enqueue-event-subject")

        logger.info(f"handle_enqueue_event.mock: {handle_enqueue_event.mock}")

        # You can check if the handler was called and what it returned
        handle_enqueue_event.mock.assert_called_once_with(message.model_dump(mode="json"))
        handle_enqueue_event.mock.assert_called_once()
