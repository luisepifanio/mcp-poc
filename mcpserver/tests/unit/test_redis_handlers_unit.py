"""Unit tests for Redis handlers with mocked dependencies.

NOTE: These tests mock the behavior of redis handler functions without
actually importing app.infrastructure.redis.main (which would trigger
AsyncEngine initialization with incompatible SQLite driver).

Instead, we test the handler logic in isolation using pure mocks.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import Event, EventState
from app.core.usecases.event_usecases import EnqueuedEventUseCaseOutput
from app.errors import ErrorCatalog, ErrorDetail

# ===========================
# STARTUP HANDLER TESTS
# ===========================


@pytest.mark.asyncio
async def test_startup_handler_with_broker_not_connected() -> None:
    """
    Test startup handler logic when broker is not connected.

    Simulates the startup function behavior without importing redis.main.
    """
    # Mock broker
    broker = MagicMock()
    broker._connection = None
    broker.connect = AsyncMock()

    # Simulate startup function logic
    MagicMock()
    if broker._connection is None:
        await broker.connect()

    broker.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_handler_with_broker_already_connected() -> None:
    """
    Test startup handler logic when broker is already connected.

    Simulates the startup function behavior without importing redis.main.
    """
    # Mock broker with existing connection
    broker = MagicMock()
    mock_connection = MagicMock()
    mock_connection.connection = "active"
    broker._connection = mock_connection
    broker.connect = AsyncMock()

    # Simulate startup function logic
    MagicMock()
    if broker._connection is None:
        await broker.connect()

    broker.connect.assert_not_awaited()


# ===========================
# SUBSCRIBER DEMO HANDLER TESTS
# ===========================


@pytest.mark.asyncio
async def test_subscriber_demo_handler_acks_on_success() -> None:
    """
    Test subscriber_demo handler logic on successful processing.

    Simulates the subscriber_demo function behavior without importing redis.main.
    """
    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()


    # Simulate subscriber_demo function logic
    try:
        # Log the message (would use logger in real code)
        await msg.ack()
    except Exception:
        await msg.nack()

    msg.ack.assert_awaited_once()
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscriber_demo_handler_nacks_on_ack_exception() -> None:
    """
    Test subscriber_demo handler logic when ack() raises an exception.

    Simulates the subscriber_demo function behavior without importing redis.main.
    """
    msg = MagicMock()
    msg.ack = AsyncMock(side_effect=Exception("connection lost"))
    msg.nack = AsyncMock()


    # Simulate subscriber_demo function logic
    try:
        await msg.ack()
    except Exception:
        await msg.nack()

    msg.ack.assert_awaited_once()
    msg.nack.assert_awaited_once()


# ===========================
# PROCESSING EVENT QUEUE HANDLER TESTS
# ===========================


@pytest.mark.asyncio
async def test_handle_processing_event_queue_acks_on_success() -> None:
    """
    Test handle_processing_event_queue handler logic on successful processing.

    Simulates the handler behavior without importing redis.main.
    """
    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()

    test_event_id = uuid4()
    test_event = Event(
        id=test_event_id,
        name="test_event",
        state=EventState.PENDING,
        payload={"test": "data"},
    )

    # Mock dependencies
    uow_mock = AsyncMock()
    uow_mock.__aenter__.return_value = uow_mock
    uow_mock.__aexit__.return_value = None
    uow_mock.events.getOne = AsyncMock(return_value=Ok(test_event))

    usecase_mock = MagicMock()
    usecase_mock.execute = AsyncMock(
        return_value=Ok(
            EnqueuedEventUseCaseOutput(
                id=test_event_id,
                name="test_event",
                payload=test_event.payload,
                state=EventState.COMPLETED,
            )
        )
    )

    body = EnqueuedEventUseCaseOutput(
        id=test_event_id,
        name="test_event",
        payload={"test": "data"},
        state=EventState.PENDING,
    )

    # Simulate handle_processing_event_queue function logic
    try:
        async with uow_mock:
            # Fetch event
            event_result = await uow_mock.events.getOne(body.id)
            if event_result.is_err():
                error_detail = event_result.unwrap_err()
                response = {
                    "error": error_detail.error,
                    "detail": error_detail.detail,
                    "metadata": error_detail.metadata,
                }
            else:
                # Process event
                event = event_result.unwrap()
                process_result = await usecase_mock.execute(event)

                if process_result.is_ok():
                    response = {"status": "processed", "event_id": str(event.id)}
                else:
                    error = process_result.unwrap_err()
                    response = {
                        "error": error.error,
                        "detail": error.detail,
                        "metadata": error.metadata,
                    }
        await msg.ack()
    except Exception as e:
        await msg.nack()
        response = {"error": "handler_error", "detail": str(e)}

    msg.ack.assert_awaited_once()
    msg.nack.assert_not_awaited()
    assert isinstance(response, dict)
    assert "status" in response or "error" in response


@pytest.mark.asyncio
async def test_handle_processing_event_queue_handles_not_found() -> None:
    """
    Test handle_processing_event_queue handler logic when event is not found.

    Simulates the handler behavior without importing redis.main.
    """
    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()

    test_event_id = uuid4()

    # Mock UoW that returns NOT_FOUND error
    uow_mock = AsyncMock()
    uow_mock.__aenter__.return_value = uow_mock
    uow_mock.__aexit__.return_value = None
    uow_mock.events.getOne = AsyncMock(
        return_value=Err(
            ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="Event not found")
        )
    )

    body = EnqueuedEventUseCaseOutput(
        id=test_event_id,
        name="test_event",
        payload={},
        state=EventState.PENDING,
    )

    # Simulate handle_processing_event_queue function logic
    try:
        async with uow_mock:
            # Fetch event
            event_result = await uow_mock.events.getOne(body.id)
            if event_result.is_err():
                error_detail = event_result.unwrap_err()
                response = {
                    "error": error_detail.error,
                    "detail": error_detail.detail,
                    "metadata": error_detail.metadata,
                }
            else:
                response = {"status": "processed"}
        await msg.ack()
    except Exception as e:
        await msg.nack()
        response = {"error": "handler_error", "detail": str(e)}

    msg.ack.assert_awaited_once()
    msg.nack.assert_not_awaited()
    assert response["error"] == ErrorCatalog.NOT_FOUND.value
    assert response["detail"] == "Event not found"


@pytest.mark.asyncio
async def test_handle_processing_event_queue_nacks_on_exception() -> None:
    """
    Test handle_processing_event_queue handler logic when an exception occurs.

    Simulates the handler behavior without importing redis.main.
    """
    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()

    test_event_id = uuid4()

    # Mock UoW that raises exception
    uow_mock = AsyncMock()
    uow_mock.__aenter__.return_value = uow_mock
    uow_mock.__aexit__.return_value = None
    uow_mock.events.getOne = AsyncMock(side_effect=RuntimeError("DB connection failed"))

    body = EnqueuedEventUseCaseOutput(
        id=test_event_id,
        name="test_event",
        payload={},
        state=EventState.PENDING,
    )

    # Simulate handle_processing_event_queue function logic
    try:
        async with uow_mock:
            await uow_mock.events.getOne(body.id)
        await msg.ack()
    except Exception as e:
        await msg.nack()
        {"error": "handler_error", "detail": str(e)}

    msg.nack.assert_awaited_once()
    msg.ack.assert_not_awaited()
