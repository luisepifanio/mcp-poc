"""Functional tests for ProcessEventUseCase2 with tenacity retry logic.

Tests cover:
1. Happy path: Success on first attempt
2. Transient error + retry: Fails then succeeds
3. Permanent error: No retry, fails immediately
4. All retries exhausted: Final failure
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from result import Ok

from app.core.entities import Event, EventState
from app.core.processors import (
    ErrorType,
    ProcessorResult,
    ProcessorResultStatus,
)
from app.core.unit_of_work import UnitOfWork
from app.core.usecases.process_event_usecase import ProcessEventUseCase2


@pytest.fixture
def test_event() -> Event:
    """Create a test event in PENDING state"""
    return Event(
        id=uuid4(),
        name="test_processor",
        state=EventState.PENDING,
        payload={"test": "data"},
    )


# ============================================================================
# Happy Path Tests
# ============================================================================


@pytest.mark.asyncio
async def test_f1_process_success_on_first_attempt(
    test_event: Event,
) -> None:
    """Functional: Event processes successfully on first attempt (no retries needed)"""
    uow_mock = MagicMock(spec=UnitOfWork)
    uow_mock.__aenter__ = AsyncMock(return_value=uow_mock)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    uow_mock.commit = AsyncMock()
    uow_mock.events.save = AsyncMock(return_value=Ok(test_event))
    uow_mock.events.getOne = AsyncMock(return_value=Ok(test_event))

    # Mock processor: success on first attempt
    processor_mock = MagicMock()
    processor_mock.__class__.__name__ = "TestProcessor"
    processor_mock.process = AsyncMock(
        return_value=ProcessorResult(
            status=ProcessorResultStatus.SUCCESS,
            data={"result": "success"},
        )
    )

    registry_mock = MagicMock(spec=dict)
    registry_mock.get = MagicMock(return_value=processor_mock)

    use_case = ProcessEventUseCase2(
        uow=uow_mock,
        processor_registry=registry_mock,
        max_attempts=3,
    )
    result = await use_case.execute(test_event)

    # Assert: Success
    assert result.is_ok()
    output = result.unwrap()
    assert output.id == test_event.id
    assert output.state == EventState.COMPLETED

    # Assert: Processor called exactly once (no retries needed)
    assert processor_mock.process.await_count == 1


# ============================================================================
# Retry Tests
# ============================================================================


@pytest.mark.asyncio
async def test_f2_process_with_transient_error_then_success() -> None:
    """Functional: Transient error on first attempt, then succeeds on retry"""
    event = Event(
        id=uuid4(),
        name="test_processor",
        state=EventState.PENDING,
        payload={"test": "data"},
    )

    uow_mock = MagicMock(spec=UnitOfWork)
    uow_mock.__aenter__ = AsyncMock(return_value=uow_mock)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    uow_mock.commit = AsyncMock()
    uow_mock.events.save = AsyncMock(return_value=Ok(event))
    uow_mock.events.getOne = AsyncMock(return_value=Ok(event))

    # Mock processor: fails once with transient error, then succeeds
    call_count = [0]

    async def processor_side_effect(_event: Event) -> ProcessorResult:
        call_count[0] += 1
        if call_count[0] == 1:
            raise ConnectionError("Transient: Connection timeout")
        return ProcessorResult(
            status=ProcessorResultStatus.SUCCESS,
            data={"result": "recovered"},
        )

    processor_mock = MagicMock()
    processor_mock.__class__.__name__ = "TestProcessor"
    processor_mock.process = AsyncMock(side_effect=processor_side_effect)
    processor_mock.classify_error = MagicMock(return_value=ErrorType.TRANSIENT)

    registry_mock = MagicMock(spec=dict)
    registry_mock.get = MagicMock(return_value=processor_mock)

    use_case = ProcessEventUseCase2(
        uow=uow_mock,
        processor_registry=registry_mock,
        max_attempts=3,
    )
    result = await use_case.execute(event)

    # Assert: Success after retry
    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.COMPLETED

    # Assert: Processor called twice (once failed, once succeeded)
    assert processor_mock.process.await_count == 2


@pytest.mark.asyncio
async def test_f3_process_with_permanent_error_no_retry() -> None:
    """Functional: Permanent error (ValueError) doesn't trigger retries"""
    event = Event(
        id=uuid4(),
        name="test_processor",
        state=EventState.PENDING,
        payload={"invalid": "payload"},
    )

    uow_mock = MagicMock(spec=UnitOfWork)
    uow_mock.__aenter__ = AsyncMock(return_value=uow_mock)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    uow_mock.commit = AsyncMock()
    uow_mock.events.save = AsyncMock(return_value=Ok(event))

    # Mock processor: raises permanent error (ValueError)
    processor_mock = MagicMock()
    processor_mock.__class__.__name__ = "TestProcessor"
    processor_mock.process = AsyncMock(side_effect=ValueError("Invalid payload"))
    processor_mock.classify_error = MagicMock(return_value=ErrorType.PERMANENT)

    registry_mock = MagicMock(spec=dict)
    registry_mock.get = MagicMock(return_value=processor_mock)

    use_case = ProcessEventUseCase2(
        uow=uow_mock,
        processor_registry=registry_mock,
        max_attempts=3,
    )
    result = await use_case.execute(event)

    # Assert: Error returned (no retry for permanent errors)
    assert result.is_err()

    # Assert: Processor called once (permanent error = no retries)
    assert processor_mock.process.await_count == 1


# ============================================================================
# Retry Exhaustion Tests
# ============================================================================


@pytest.mark.asyncio
async def test_f4_all_retries_exhausted() -> None:
    """Functional: After 3 retry attempts exhausted, returns error"""
    event = Event(
        id=uuid4(),
        name="test_processor",
        state=EventState.PENDING,
        payload={"test": "data"},
    )

    uow_mock = MagicMock(spec=UnitOfWork)
    uow_mock.__aenter__ = AsyncMock(return_value=uow_mock)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    uow_mock.commit = AsyncMock()
    uow_mock.events.save = AsyncMock(return_value=Ok(event))

    # Mock processor: always fails with transient error
    processor_mock = MagicMock()
    processor_mock.__class__.__name__ = "TestProcessor"
    processor_mock.process = AsyncMock(
        side_effect=ConnectionError("Persistent connection timeout")
    )
    processor_mock.classify_error = MagicMock(return_value=ErrorType.TRANSIENT)

    registry_mock = MagicMock(spec=dict)
    registry_mock.get = MagicMock(return_value=processor_mock)

    use_case = ProcessEventUseCase2(
        uow=uow_mock,
        processor_registry=registry_mock,
        max_attempts=3,
    )
    result = await use_case.execute(event)

    # Assert: Error returned (all retries exhausted)
    assert result.is_err()
    error = result.unwrap_err()
    # Error from last attempt
    assert error.metadata.get("error_type") == "transient"

    # Assert: Processor called 3 times (max attempts reached)
    assert processor_mock.process.await_count == 3


# ============================================================================
# State Transition Tests
# ============================================================================


@pytest.mark.asyncio
async def test_f5_event_state_transitions_correctly() -> None:
    """Functional: Event state transitions PENDING → PROCESSING → COMPLETED"""
    event = Event(
        id=uuid4(),
        name="test_processor",
        state=EventState.PENDING,
        payload={"test": "data"},
    )

    # Track state transitions
    saved_events: list[Event] = []

    async def save_side_effect(evt: Event):
        saved_events.append(evt)
        return Ok(evt)

    uow_mock = MagicMock(spec=UnitOfWork)
    uow_mock.__aenter__ = AsyncMock(return_value=uow_mock)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    uow_mock.commit = AsyncMock()
    uow_mock.events.save = AsyncMock(side_effect=save_side_effect)

    processor_mock = MagicMock()
    processor_mock.__class__.__name__ = "TestProcessor"
    processor_mock.process = AsyncMock(
        return_value=ProcessorResult(
            status=ProcessorResultStatus.SUCCESS,
            data={"result": "ok"},
        )
    )

    registry_mock = MagicMock(spec=dict)
    registry_mock.get = MagicMock(return_value=processor_mock)

    use_case = ProcessEventUseCase2(
        uow=uow_mock,
        processor_registry=registry_mock,
        max_attempts=3,
    )
    result = await use_case.execute(event)

    # Assert: Final state is COMPLETED
    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.COMPLETED

    # Assert: State transitions persisted
    # First save: lock PENDING → PROCESSING
    # Second save: final state PENDING → COMPLETED
    assert len(saved_events) >= 2
    assert saved_events[-1].state == EventState.COMPLETED


@pytest.mark.asyncio
async def test_f6_process_event_in_retrying_state() -> None:
    """Functional: Event in RETRYING state can be reprocessed"""
    event = Event(
        id=uuid4(),
        name="test_processor",
        state=EventState.RETRYING,  # ← Already in RETRYING from previous attempt
        payload={"test": "data"},
    )

    uow_mock = MagicMock(spec=UnitOfWork)
    uow_mock.__aenter__ = AsyncMock(return_value=uow_mock)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    uow_mock.commit = AsyncMock()
    uow_mock.events.save = AsyncMock(return_value=Ok(event))

    processor_mock = MagicMock()
    processor_mock.__class__.__name__ = "TestProcessor"
    processor_mock.process = AsyncMock(
        return_value=ProcessorResult(
            status=ProcessorResultStatus.SUCCESS,
            data={"result": "recovered"},
        )
    )

    registry_mock = MagicMock(spec=dict)
    registry_mock.get = MagicMock(return_value=processor_mock)

    use_case = ProcessEventUseCase2(
        uow=uow_mock,
        processor_registry=registry_mock,
        max_attempts=3,
    )
    result = await use_case.execute(event)

    # Assert: Reprocessing succeeds
    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.COMPLETED
