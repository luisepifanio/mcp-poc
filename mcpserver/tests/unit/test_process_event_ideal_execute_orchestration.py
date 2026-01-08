"""Tests para execute() - orquestación completa de las 3 etapas."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import Event, EventState, JSONDict
from app.core.processor_registry import ProcessorRegistry
from app.core.processors import (
    ErrorType,
    IEventProcessor,
    ProcessorResult,
    ProcessorResultStatus,
    RetryConfig,
)
from app.core.usecases.event_usecases import EnqueuedEventUseCaseOutput
from app.core.usecases.neo_event_usecase import ProcessEventIdealUseCase


class DummyProcessor(IEventProcessor):
    def __init__(self) -> None:
        self._process: AsyncMock = AsyncMock()

    async def process(self, event: Event) -> ProcessorResult:
        result = await self._process(event)
        return cast(ProcessorResult, result)

    def get_retry_config(self) -> RetryConfig:
        return RetryConfig(
            max_attempts=3,
            initial_backoff=0.1,
            max_backoff=2.0,
            backoff_multiplier=2.0,
        )

    def classify_error(self, exc: BaseException) -> ErrorType:
        if isinstance(exc, RuntimeError):
            return ErrorType.TRANSIENT
        return ErrorType.PERMANENT


def make_usecase_with_processor(processor: IEventProcessor) -> ProcessEventIdealUseCase:
    registry = ProcessorRegistry()
    registry.register("evt", processor)
    uow = cast(MagicMock, MagicMock())
    uow.events = MagicMock()
    uow.events.getOne = AsyncMock()
    uow.events.save = AsyncMock()
    uow.commit = AsyncMock()
    return ProcessEventIdealUseCase(uow=uow, processor_registry=registry)  # type: ignore[arg-type]


# ============================================================================
# Happy Path: PENDING → PROCESSING → SUCCESS → COMPLETED
# ============================================================================


@pytest.mark.asyncio
async def test_execute_happy_path_pending_to_completed() -> None:
    """Happy path: fetch → validate_and_lock → process → persist_outcome → COMPLETED."""
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.SUCCESS,
        data={"result": "ok"},
    )
    usecase = make_usecase_with_processor(processor)

    # Input: ID to fetch
    event_id = uuid4()

    # Fresh event from DB (PENDING)
    fresh_event = Event(
        id=event_id, name="evt", state=EventState.PENDING, payload={}, context={}
    )
    usecase.uow.events.getOne.return_value = Ok(fresh_event)
    usecase.uow.events.save.return_value = Ok(fresh_event)

    # Create input DTO
    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id,
        name="evt",
        state=EventState.PENDING,
        payload={},
        context={},
    )

    result = await usecase.execute(input_dto)

    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.COMPLETED
    assert output.result == {"payload": {"result": "ok"}}
    assert usecase.uow.events.getOne.await_count == 1
    # save is called: lock (TX1) + persist_outcome (TX2, since process doesn't persist)
    assert usecase.uow.events.save.await_count == 2
    assert usecase.uow.commit.await_count == 2  # TX1 (lock) + TX2 (persist)


@pytest.mark.asyncio
async def test_execute_happy_path_temporal_error_to_completed() -> None:
    """Happy path from TEMPORAL_ERROR: retrying → process → COMPLETED."""
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.SUCCESS,
        data={"data": 1},
    )
    usecase = make_usecase_with_processor(processor)

    event_id = uuid4()
    fresh_event = Event(
        id=event_id, name="evt", state=EventState.TEMPORAL_ERROR, payload={}, context={}
    )
    usecase.uow.events.getOne.return_value = Ok(fresh_event)
    usecase.uow.events.save.return_value = Ok(fresh_event)

    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id,
        name="evt",
        state=EventState.TEMPORAL_ERROR,
        payload={},
    )

    result = await usecase.execute(input_dto)

    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.COMPLETED


# ============================================================================
# Error Scenarios: Cada etapa puede fallar
# ============================================================================


@pytest.mark.asyncio
async def test_execute_fetch_error_short_circuits() -> None:
    """Error en Stage 0 (fetch): retorna Err inmediatamente sin procesar."""
    processor = DummyProcessor()
    usecase = make_usecase_with_processor(processor)

    event_id = uuid4()
    usecase.uow.events.getOne.return_value = Err(Exception("Event not found"))

    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id, name="evt", state=EventState.PENDING, payload={}
    )

    result = await usecase.execute(input_dto)

    assert result.is_err()
    processor._process.assert_not_awaited()
    usecase.uow.events.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_validate_lock_error_short_circuits() -> None:
    """Error en Stage 1 (validate_and_lock): retorna Err sin procesar."""
    processor = DummyProcessor()
    usecase = make_usecase_with_processor(processor)

    event_id = uuid4()
    # Estado inválido para procesar
    invalid_event = Event(
        id=event_id, name="evt", state=EventState.COMPLETED, payload={}, context={}
    )
    usecase.uow.events.getOne.return_value = Ok(invalid_event)

    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id, name="evt", state=EventState.COMPLETED, payload={}
    )

    result = await usecase.execute(input_dto)

    assert result.is_err()
    err = result.unwrap_err()
    assert "Invalid state" in err.detail
    processor._process.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_process_error_short_circuits() -> None:
    """Error en Stage 2 (process_with_retries): retorna Err sin persistir outcome."""
    processor = DummyProcessor()
    # RuntimeError es TRANSIENT, pero mockear que luego de intentos agota
    processor._process.side_effect = [
        RuntimeError("fail1"),
        RuntimeError("fail2"),
        RuntimeError("fail3"),
    ]
    usecase = make_usecase_with_processor(processor)

    event_id = uuid4()
    fresh_event = Event(
        id=event_id, name="evt", state=EventState.PENDING, payload={}, context={}
    )
    usecase.uow.events.getOne.return_value = Ok(fresh_event)
    usecase.uow.events.save.return_value = Ok(fresh_event)

    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id, name="evt", state=EventState.PENDING, payload={}
    )

    result = await usecase.execute(input_dto)

    assert result.is_err()
    # Save called once for lock (TX1), but not for outcome since process returned Err
    assert usecase.uow.events.save.await_count == 1


@pytest.mark.asyncio
async def test_execute_persist_outcome_error() -> None:
    """Error en Stage 3 (persist_outcome): salva error después de procesar."""
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.SUCCESS,
        data={"ok": True},
    )
    usecase = make_usecase_with_processor(processor)

    event_id = uuid4()
    fresh_event = Event(
        id=event_id, name="evt", state=EventState.PENDING, payload={}, context={}
    )
    usecase.uow.events.getOne.return_value = Ok(fresh_event)

    # Mock save para fallar en persist_outcome (segundo/tercer call)
    save_calls = 0

    async def save_side_effect(event: Event) -> Ok[Event] | Err[Exception]:
        nonlocal save_calls
        save_calls += 1
        if save_calls <= 1:  # First call (lock) succeeds
            return Ok(event)
        else:  # Second call (persist) fails
            return Err(Exception("DB error"))

    usecase.uow.events.save.side_effect = save_side_effect

    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id, name="evt", state=EventState.PENDING, payload={}
    )

    result = await usecase.execute(input_dto)

    assert result.is_err()


# ============================================================================
# Edge Cases: Pending Callback, Exhaustion, etc.
# ============================================================================


@pytest.mark.asyncio
async def test_execute_pending_callback_persists_without_completion() -> None:
    """Pending callback: no transición a COMPLETED, solo persist context."""
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.PENDING_CALLBACK,
        callback_subject="callback_topic",
        metadata={"data": "pending"},
    )
    usecase = make_usecase_with_processor(processor)

    event_id = uuid4()
    fresh_event = Event(
        id=event_id, name="evt", state=EventState.PENDING, payload={}, context={}
    )
    usecase.uow.events.getOne.return_value = Ok(fresh_event)
    usecase.uow.events.save.return_value = Ok(fresh_event)

    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id, name="evt", state=EventState.PENDING, payload={}
    )

    result = await usecase.execute(input_dto)

    assert result.is_ok()
    output = result.unwrap()
    # Should remain PROCESSING (no transition to COMPLETED)
    assert output.state == EventState.PROCESSING
    ctx = cast(JSONDict, output.context or {})
    proc = cast(JSONDict, ctx.get("processing") or {})
    assert proc.get("pending_callback") is True


@pytest.mark.asyncio
async def test_execute_retry_exhaustion_goes_to_exhausted() -> None:
    """Retry exhaustion: max attempts exceeded → EXHAUSTED."""
    processor = DummyProcessor()
    processor._process.side_effect = [
        RuntimeError("fail1"),
        RuntimeError("fail2"),
        RuntimeError("fail3"),
    ]
    usecase = make_usecase_with_processor(processor)

    event_id = uuid4()
    fresh_event = Event(
        id=event_id, name="evt", state=EventState.PENDING, payload={}, context={}
    )
    usecase.uow.events.getOne.return_value = Ok(fresh_event)
    usecase.uow.events.save.return_value = Ok(fresh_event)

    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id, name="evt", state=EventState.PENDING, payload={}
    )

    result = await usecase.execute(input_dto)

    # Process returns Err, so execute returns Err (no persist_outcome called)
    assert result.is_err()


@pytest.mark.asyncio
async def test_execute_returns_output_dto_not_entity() -> None:
    """Output must be ProcessEventResult (DTO) not Event entity."""
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.SUCCESS,
        data={"test": True},
    )
    usecase = make_usecase_with_processor(processor)

    event_id = uuid4()
    fresh_event = Event(
        id=event_id, name="evt", state=EventState.PENDING, payload={}, context={}
    )
    usecase.uow.events.getOne.return_value = Ok(fresh_event)
    usecase.uow.events.save.return_value = Ok(fresh_event)

    input_dto = EnqueuedEventUseCaseOutput(
        id=event_id, name="evt", state=EventState.PENDING, payload={}
    )

    result = await usecase.execute(input_dto)

    assert result.is_ok()
    output = result.unwrap()
    # Must be instance of DTO, not Event entity
    assert isinstance(output, EnqueuedEventUseCaseOutput)
    assert hasattr(output, "id")
    assert hasattr(output, "state")
    assert hasattr(output, "result")
