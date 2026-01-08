"""Tests para cobertura de ramas críticas faltantes en process_with_retries y persist_outcome."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.entities import Event, EventState, EventTransition, JSONDict
from app.core.processor_registry import ProcessorRegistry
from app.core.processors import (
    ErrorType,
    IEventProcessor,
    ProcessorResult,
    ProcessorResultStatus,
    RetryConfig,
)
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
    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock()
    uow.commit = AsyncMock()
    return ProcessEventIdealUseCase(uow=uow, processor_registry=registry)


# ============================================================================
# Tests para proceso_with_retries: ramas faltantes
# ============================================================================


@pytest.mark.asyncio
async def test_pending_callback_with_none_metadata() -> None:
    """Rama faltante: PENDING_CALLBACK cuando metadata es None."""
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.PENDING_CALLBACK,
        callback_subject="cb",
        metadata=None,  # ← metadata es None
    )
    usecase = make_usecase_with_processor(processor)
    event = Event(id=uuid4(), name="evt", state=EventState.PROCESSING, payload={}, context={})

    result = await usecase.process_with_retries(event)

    assert result.is_ok()
    ev = result.unwrap()
    context = cast(JSONDict, ev.context or {})
    proc_ctx = cast(JSONDict, context.get("processing") or {})
    assert proc_ctx["pending_callback"] is True
    assert proc_ctx["callback_subject"] == "cb"
    assert "metadata" not in proc_ctx  # No debe estar si era None


@pytest.mark.asyncio
async def test_processor_failed_with_none_error() -> None:
    """Rama faltante: ProcessorResultStatus.FAILED cuando error es None."""
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.FAILED,
        error=None,  # ← error es None, debe usar default "Processor failed"
    )
    usecase = make_usecase_with_processor(processor)
    event = Event(id=uuid4(), name="evt", state=EventState.PROCESSING, payload={}, context={})

    result = await usecase.process_with_retries(event)

    assert result.is_err()
    err = result.unwrap_err()
    assert "Processor failed" in err.detail  # Usa el default
    assert event.state == EventState.TEMPORAL_ERROR


@pytest.mark.asyncio
async def test_processor_failed_from_retrying_state() -> None:
    """Rama faltante: FAILED desde RETRYING (no solo PROCESSING)."""
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.FAILED,
        error="boom",
    )
    usecase = make_usecase_with_processor(processor)
    event = Event(id=uuid4(), name="evt", state=EventState.RETRYING, payload={}, context={})

    result = await usecase.process_with_retries(event)

    assert result.is_err()
    assert event.state == EventState.TEMPORAL_ERROR


@pytest.mark.asyncio
async def test_exception_from_retrying_state() -> None:
    """Rama faltante: Exception desde RETRYING estado transiciona correctamente."""
    processor = DummyProcessor()
    # RuntimeError es TRANSIENT, pero mockear un fallo que no se reintenta
    processor._process.side_effect = RuntimeError("boom")
    usecase = make_usecase_with_processor(processor)
    event = Event(id=uuid4(), name="evt", state=EventState.RETRYING, payload={}, context={})

    # RuntimeError es TRANSIENT, reintenta hasta agotar
    result = await usecase.process_with_retries(event)

    assert result.is_err()
    assert event.state == EventState.TEMPORAL_ERROR
    context = cast(JSONDict, event.context or {})
    proc_ctx = cast(JSONDict, context.get("processing") or {})
    # Con max_attempts=3, debe haber 3 intentos registrados
    attempts = cast(list[JSONDict], proc_ctx.get("attempts") or [])
    assert len(attempts) == 3
    for attempt in attempts:
        assert "boom" in attempt["error"]


@pytest.mark.asyncio
async def test_retries_exhaust_before_success_from_retrying() -> None:
    """Rama faltante: Agotamiento comenzando desde estado RETRYING."""
    processor = DummyProcessor()
    processor._process.side_effect = [
        RuntimeError("fail1"),
        RuntimeError("fail2"),
        RuntimeError("fail3"),
    ]
    usecase = make_usecase_with_processor(processor)
    event = Event(id=uuid4(), name="evt", state=EventState.RETRYING, payload={}, context={})

    result = await usecase.process_with_retries(event)

    assert result.is_err()
    assert event.state == EventState.TEMPORAL_ERROR
    context = cast(JSONDict, event.context or {})
    proc_ctx = cast(JSONDict, context.get("processing") or {})
    assert proc_ctx["retry_exhausted"] is True


# ============================================================================
# Tests para persist_outcome: ramas faltantes
# ============================================================================


@pytest.mark.asyncio
async def test_persist_outcome_save_error_returns_err() -> None:
    """Rama faltante: Cuando uow.events.save retorna Err en SUCCESS case."""
    from result import Err

    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock(return_value=Err(Exception("db error")))
    uow.commit = AsyncMock()

    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(id=uuid4(), name="evt", state=EventState.PROCESSING, payload={}, context={})
    event.result = {"payload": {"ok": True}}

    result = await usecase.persist_outcome(event)

    assert result.is_err()
    uow.events.save.assert_awaited()
    uow.commit.assert_not_awaited()  # No debe commitear si save falló


@pytest.mark.asyncio
async def test_persist_outcome_pending_callback_save_error() -> None:
    """Rama faltante: Save error en PENDING_CALLBACK case."""
    from result import Err

    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock(return_value=Err(Exception("db error")))
    uow.commit = AsyncMock()

    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(id=uuid4(), name="evt", state=EventState.RETRYING, payload={}, context={})
    event.context = {"processing": {"pending_callback": True}}

    result = await usecase.persist_outcome(event)

    assert result.is_err()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_outcome_exhausted_save_error() -> None:
    """Rama faltante: Save error en RETRY_EXHAUSTED case."""
    from result import Err

    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock(return_value=Err(Exception("db error")))
    uow.commit = AsyncMock()

    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(id=uuid4(), name="evt", state=EventState.TEMPORAL_ERROR, payload={}, context={})
    event.transitions = [
        EventTransition(event_id=event.id, from_state=EventState.RETRYING, to_state=EventState.TEMPORAL_ERROR)
    ]
    event.context = {"processing": {"retry_exhausted": True}}

    result = await usecase.persist_outcome(event)

    assert result.is_err()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_outcome_default_temporal_error_save_error() -> None:
    """Rama faltante: Save error en default TEMPORAL_ERROR case."""
    from result import Err

    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock(return_value=Err(Exception("db error")))
    uow.commit = AsyncMock()

    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(id=uuid4(), name="evt", state=EventState.TEMPORAL_ERROR, payload={}, context={})

    result = await usecase.persist_outcome(event)

    assert result.is_err()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_outcome_success_from_retrying_with_no_transition() -> None:
    """Rama faltante: SUCCESS desde estado que no es PROCESSING/RETRYING."""
    from result import Ok

    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock()
    uow.commit = AsyncMock()

    usecase = ProcessEventIdealUseCase(uow=uow)
    # Evento ya en estado COMPLETED (edge case: idempotencia)
    event = Event(id=uuid4(), name="evt", state=EventState.COMPLETED, payload={}, context={})
    event.result = {"payload": {"ok": True}}

    uow.events.save.return_value = Ok(event)

    result = await usecase.persist_outcome(event)

    assert result.is_ok()
    # No debe transicionar (ya está en COMPLETED)
    assert event.state == EventState.COMPLETED
    uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_persist_outcome_exhausted_no_transition_from_processing() -> None:
    """Rama faltante: EXHAUSTED cuando el último from_state es PROCESSING (no RETRYING)."""
    from result import Ok

    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock(return_value=Ok(None))
    uow.commit = AsyncMock()

    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(id=uuid4(), name="evt", state=EventState.TEMPORAL_ERROR, payload={}, context={})
    # Simular que el evento fue de PROCESSING → TEMPORAL_ERROR (no RETRYING)
    event.transitions = [
        EventTransition(event_id=event.id, from_state=EventState.PROCESSING, to_state=EventState.TEMPORAL_ERROR)
    ]
    event.context = {"processing": {"retry_exhausted": True, "attempts": [{}]}}

    result = await usecase.persist_outcome(event)

    # Debe persitir sin cambiar el estado (PROCESSING no puede ir a EXHAUSTED según la máquina de estados)
    assert result.is_ok()
    assert event.state == EventState.TEMPORAL_ERROR
    ctx = cast(JSONDict, event.context or {})
    proc = cast(JSONDict, ctx.get("processing") or {})
    assert proc.get("retry_count") == 1
