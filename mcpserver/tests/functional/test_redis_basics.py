import logging
from typing import Any
from unittest.mock import MagicMock
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

        # ✅ 1. Verificar que .mock existe y luego hacer assertions
        assert hasattr(subscriber_demo, "mock"), (
            "subscriber_demo should have .mock in test context"
        )
        # ✅ 2. Verificar que .mock es una instancia de MagicMock
        assert isinstance(subscriber_demo.mock, MagicMock), (
            "subscriber_demo.mock should be a MagicMock"
        )

        # ✅ 3. Con este contexto puedes realizar asssertions sin type check errors

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

        # ✅ 1. Verificar que .mock existe y luego hacer assertions
        assert hasattr(handle_enqueue_event, "mock"), (
            "handle_enqueue_event should have .mock in test context"
        )
        # ✅ 2. Verificar que .mock es una instancia de MagicMock
        assert isinstance(handle_enqueue_event.mock, MagicMock), (
            "handle_enqueue_event.mock should be a MagicMock"
        )

        # ✅ 3. Con este contexto puedes realizar asssertions sin type check errors

        logger.info(f"handle_enqueue_event.mock: {handle_enqueue_event.mock}")

        # You can check if the handler was called and what it returned
        handle_enqueue_event.mock.assert_called_once_with(message.model_dump(mode="json"))
        handle_enqueue_event.mock.assert_called_once()
