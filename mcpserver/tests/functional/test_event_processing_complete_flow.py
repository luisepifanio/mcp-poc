"""
Integration tests for complete event processing flow.

Tests end-to-end scenarios:
1. Happy path: PENDING → PROCESSING → COMPLETED
2. Sync processor error (transient): → TEMPORAL_ERROR → RETRYING → COMPLETED
3. Sync processor error (permanent): → FAILED (no retry)
4. Long-running task: → PROCESSING (callback) → COMPLETED
5. Validation error: → FAILED (no retry)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.entities import Event, EventState
from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseOutput,
)
from app.infrastructure.redis.main import handle_processing_event_queue


@pytest.fixture
def broker_mock() -> MagicMock:
    """Fixture: Mock RedisBroker"""
    mock = MagicMock()
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
async def setup_flow_mocks() -> dict[str, MagicMock]:
    """Fixture: Setup common mocks for flow tests"""

    def create_uow_mock(event: Event | None = None) -> MagicMock:
        """Factory for UoW mock with event"""
        from result import Err, Ok

        from app.errors import ErrorCatalog, ErrorDetail

        uow = AsyncMock()
        uow.__aenter__.return_value = uow
        uow.__aexit__.return_value = None
        if event:
            uow.events.getOne = AsyncMock(return_value=Ok(event))
        else:
            uow.events.getOne = AsyncMock(
                return_value=Err(
                    ErrorDetail(
                        error=ErrorCatalog.NOT_FOUND.value, detail="Event not found"
                    )
                )
            )
        return uow

    return {"create_uow_mock": create_uow_mock}


# ============================================================================
# Happy Path: PENDING → PROCESSING → COMPLETED
# ============================================================================


@pytest.mark.asyncio
async def test_flow_happy_path_sync_processor_success(
    setup_flow_mocks: dict[str, MagicMock],
) -> None:
    """
    Test: Happy path - sync processor succeeds.

    Flow:
    1. Event received in PENDING state
    2. Processor executes and returns SUCCESS
    3. Event transitions to COMPLETED
    4. Message is ack'd
    """
    from app.infrastructure.processors.sync_processors import ApiCallProcessor

    event = Event(
        id=uuid4(),
        name="api_call",
        state=EventState.PENDING,
        payload={"method": "GET", "url": "https://api.example.com/test"},
    )

    msg_mock = MagicMock()
    msg_mock.ack = AsyncMock()
    msg_mock.nack = AsyncMock()

    session_mock = AsyncMock()

    with patch("app.infrastructure.redis.main.AsyncSQLAlchemyUnitOfWork") as uow_class:
        uow = setup_flow_mocks["create_uow_mock"](event)
        uow_class.return_value = uow

        with patch("app.infrastructure.redis.main.processor_registry") as registry:
            processor = ApiCallProcessor()
            registry.get.return_value = processor

            with patch("app.infrastructure.redis.main.ProcessEventUseCase") as usecase:
                usecase_inst = AsyncMock()
                usecase.return_value = usecase_inst

                body = EnqueuedEventUseCaseOutput(
                    id=event.id,
                    name="api_call",
                    payload=event.payload,
                    state=EventState.PENDING,
                )

                # Mock processor.process() to return success
                with patch.object(processor, "process") as process_mock:
                    from app.core.processors import ProcessorResult, ProcessorResultStatus

                    process_mock.return_value = ProcessorResult(
                        status=ProcessorResultStatus.SUCCESS,
                        data={"status": "ok"},
                    )

                    result = await handle_processing_event_queue(
                        body, msg_mock, session_mock
                    )

                    # Verify ack was called
                    msg_mock.ack.assert_awaited_once()
                    msg_mock.nack.assert_not_awaited()

                    # Verify result returned
                    assert result is not None
                    assert result["event_id"] == str(event.id)
                    assert result["processed"] is True


# ============================================================================
# Error Path: PENDING → TEMPORAL_ERROR → RETRYING
# ============================================================================


@pytest.mark.asyncio
async def test_flow_transient_error_sync_processor(
    setup_flow_mocks: dict[str, MagicMock],
) -> None:
    """
    Test: Transient error triggers retry logic.

    Flow:
    1. Event received in PENDING state
    2. Processor raises transient error (connection timeout)
    3. Error is classified as TRANSIENT
    4. Event transitions to TEMPORAL_ERROR
    5. Message is ack'd (will be retried)
    """
    from app.infrastructure.processors.sync_processors import ApiCallProcessor

    event = Event(
        id=uuid4(),
        name="api_call",
        state=EventState.PENDING,
        payload={"method": "GET", "url": "https://api.example.com/test"},
    )

    msg_mock = MagicMock()
    msg_mock.ack = AsyncMock()
    msg_mock.nack = AsyncMock()

    session_mock = AsyncMock()

    with patch("app.infrastructure.redis.main.AsyncSQLAlchemyUnitOfWork") as uow_class:
        uow = setup_flow_mocks["create_uow_mock"](event)
        uow_class.return_value = uow

        with patch("app.infrastructure.redis.main.processor_registry") as registry:
            processor = ApiCallProcessor()
            registry.get.return_value = processor

            with patch("app.infrastructure.redis.main.ProcessEventUseCase") as usecase:
                usecase_inst = AsyncMock()
                usecase.return_value = usecase_inst

                body = EnqueuedEventUseCaseOutput(
                    id=event.id,
                    name="api_call",
                    payload=event.payload,
                    state=EventState.PENDING,
                )

                # Mock processor.process() to raise transient error
                with patch.object(processor, "process") as process_mock:
                    import httpx

                    process_mock.side_effect = httpx.TimeoutException("Request timeout")

                    await handle_processing_event_queue(body, msg_mock, session_mock)

                    # Verify ack was called
                    msg_mock.ack.assert_awaited_once()

                    # Verify ProcessEventUseCase was called with is_temporal_error=True
                    usecase_inst.execute.assert_awaited_once()
                    call_kwargs = usecase_inst.execute.call_args[1]
                    assert call_kwargs.get("is_temporal_error") is True


# ============================================================================
# Permanent Error: PENDING → FAILED
# ============================================================================


@pytest.mark.asyncio
async def test_flow_permanent_error_no_retry(
    setup_flow_mocks: dict[str, MagicMock],
) -> None:
    """
    Test: Permanent error (validation) doesn't retry.

    Flow:
    1. Event received in PENDING state
    2. Processor raises ValueError (validation error)
    3. Error is classified as PERMANENT
    4. Event transitions directly to FAILED
    5. Message is ack'd
    """
    from app.infrastructure.processors.sync_processors import ApiCallProcessor

    event = Event(
        id=uuid4(),
        name="api_call",
        state=EventState.PENDING,
        payload={"method": "INVALID", "url": "https://api.example.com/test"},
    )

    msg_mock = MagicMock()
    msg_mock.ack = AsyncMock()
    msg_mock.nack = AsyncMock()

    session_mock = AsyncMock()

    with patch("app.infrastructure.redis.main.AsyncSQLAlchemyUnitOfWork") as uow_class:
        uow = setup_flow_mocks["create_uow_mock"](event)
        uow_class.return_value = uow

        with patch("app.infrastructure.redis.main.processor_registry") as registry:
            processor = ApiCallProcessor()
            registry.get.return_value = processor

            with patch("app.infrastructure.redis.main.ProcessEventUseCase") as usecase:
                usecase_inst = AsyncMock()
                usecase.return_value = usecase_inst

                body = EnqueuedEventUseCaseOutput(
                    id=event.id,
                    name="api_call",
                    payload=event.payload,
                    state=EventState.PENDING,
                )

                # Mock processor.process() to raise validation error
                with patch.object(processor, "process") as process_mock:
                    process_mock.side_effect = ValueError("Invalid HTTP method")

                    await handle_processing_event_queue(body, msg_mock, session_mock)

                    # Verify ack was called
                    msg_mock.ack.assert_awaited_once()

                    # Verify ProcessEventUseCase was called with is_failed=True
                    usecase_inst.execute.assert_awaited_once()
                    call_kwargs = usecase_inst.execute.call_args[1]
                    assert call_kwargs.get("is_failed") is True


# ============================================================================
# Async Long-Running: PENDING → PROCESSING (awaiting callback)
# ============================================================================


@pytest.mark.asyncio
async def test_flow_long_running_processor_callback(
    setup_flow_mocks: dict[str, MagicMock],
) -> None:
    """
    Test: Long-running processor publishes task and awaits callback.

    Flow:
    1. Event received in PENDING state
    2. Processor executes and publishes task (returns PENDING_CALLBACK)
    3. Event transitions to PROCESSING (awaiting callback)
    4. Callback subject stored in context
    5. Message is ack'd
    """
    event = Event(
        id=uuid4(),
        name="scraping_task",
        state=EventState.PENDING,
        payload={"url": "https://example.com", "selectors": ["h1", "p"]},
    )

    msg_mock = MagicMock()
    msg_mock.ack = AsyncMock()
    msg_mock.nack = AsyncMock()

    session_mock = AsyncMock()

    with patch("app.infrastructure.redis.main.AsyncSQLAlchemyUnitOfWork") as uow_class:
        uow = setup_flow_mocks["create_uow_mock"](event)
        uow_class.return_value = uow

        with patch("app.infrastructure.redis.main.processor_registry") as registry:
            from app.infrastructure.processors.long_running_processor import (
                LongRunningTaskProcessor,
            )

            broker_mock = MagicMock()
            broker_mock.publish = AsyncMock()

            processor = LongRunningTaskProcessor(
                broker_mock, task_subject="scraping-tasks"
            )
            registry.get.return_value = processor

            with patch("app.infrastructure.redis.main.ProcessEventUseCase") as usecase:
                usecase_inst = AsyncMock()
                usecase.return_value = usecase_inst

                body = EnqueuedEventUseCaseOutput(
                    id=event.id,
                    name="scraping_task",
                    payload=event.payload,
                    state=EventState.PENDING,
                )

                await handle_processing_event_queue(body, msg_mock, session_mock)

                # Verify ack was called
                msg_mock.ack.assert_awaited_once()

                # Verify ProcessEventUseCase was called (not with is_failed or is_temporal_error)
                usecase_inst.execute.assert_awaited_once()
                call_kwargs = usecase_inst.execute.call_args[1]
                assert call_kwargs.get("is_failed") is not True
                assert call_kwargs.get("is_temporal_error") is not True


# ============================================================================
# Event Not Found
# ============================================================================


@pytest.mark.asyncio
async def test_flow_event_not_found_nack() -> None:
    """
    Test: Event not found in database -> nack message.

    Flow:
    1. Event ID received but not found in database
    2. Nack message for redelivery
    3. Return None
    """
    msg_mock = MagicMock()
    msg_mock.ack = AsyncMock()
    msg_mock.nack = AsyncMock()

    session_mock = AsyncMock()
    event_id = uuid4()

    with patch("app.infrastructure.redis.main.AsyncSQLAlchemyUnitOfWork") as uow_class:
        from result import Err

        from app.errors import ErrorCatalog, ErrorDetail

        uow = AsyncMock()
        uow.__aenter__.return_value = uow
        uow.__aexit__.return_value = None
        uow.events.getOne = AsyncMock(
            return_value=Err(
                ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="Event not found")
            )
        )  # Event not found
        uow_class.return_value = uow

        body = EnqueuedEventUseCaseOutput(
            id=event_id,
            name="unknown_event",
            payload={},
            state=EventState.PENDING,
        )

        result = await handle_processing_event_queue(body, msg_mock, session_mock)

        # Verify nack was called
        msg_mock.nack.assert_awaited_once()
        assert result is None
