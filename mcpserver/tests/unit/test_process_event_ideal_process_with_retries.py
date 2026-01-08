from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.entities import Event, EventState, JSONDict
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


@pytest.mark.asyncio
async def test_process_success_sets_result() -> None:
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.SUCCESS,
        data={"ok": True},
    )
    usecase = make_usecase_with_processor(processor)
    event = Event(
        id=uuid4(), name="evt", state=EventState.PROCESSING, payload={}, context={}
    )

    result = await usecase.process_with_retries(event)

    assert result.is_ok()
    ev = result.unwrap()
    assert ev.result == {"payload": {"ok": True}}
    context = cast(JSONDict, ev.context or {})
    proc_ctx = cast(JSONDict, context.get("processing") or {})
    assert proc_ctx["processor"] == processor.__class__.__name__
    assert "last_activity" in proc_ctx


@pytest.mark.asyncio
async def test_pending_callback_sets_pending_flag() -> None:
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.PENDING_CALLBACK,
        callback_subject="cb",
        metadata={"m": 1},
    )
    usecase = make_usecase_with_processor(processor)
    event = Event(
        id=uuid4(), name="evt", state=EventState.RETRYING, payload={}, context={}
    )

    result = await usecase.process_with_retries(event)

    assert result.is_ok()
    ev = result.unwrap()
    context = cast(JSONDict, ev.context or {})
    proc_ctx = cast(JSONDict, context.get("processing") or {})
    assert proc_ctx["pending_callback"] is True
    assert proc_ctx["callback_subject"] == "cb"
    assert proc_ctx["metadata"] == {"m": 1}


@pytest.mark.asyncio
async def test_failed_marks_temporal_error_and_err() -> None:
    processor = DummyProcessor()
    processor._process.return_value = ProcessorResult(
        status=ProcessorResultStatus.FAILED,
        error="boom",
    )
    usecase = make_usecase_with_processor(processor)
    event = Event(
        id=uuid4(), name="evt", state=EventState.PROCESSING, payload={}, context={}
    )

    result = await usecase.process_with_retries(event)

    assert result.is_err()
    assert event.state == EventState.TEMPORAL_ERROR
    context = cast(JSONDict, event.context or {})
    proc_ctx = cast(JSONDict, context.get("processing") or {})
    assert proc_ctx["pending_callback"] is False


@pytest.mark.asyncio
async def test_transient_exception_retries_then_succeeds() -> None:
    processor = DummyProcessor()
    processor._process.side_effect = [
        RuntimeError("boom"),
        ProcessorResult(status=ProcessorResultStatus.SUCCESS, data={"ok": 1}),
    ]
    usecase = make_usecase_with_processor(processor)
    event = Event(
        id=uuid4(), name="evt", state=EventState.PROCESSING, payload={}, context={}
    )

    result = await usecase.process_with_retries(event)

    assert result.is_ok()
    assert event.state == EventState.TEMPORAL_ERROR
    context = cast(JSONDict, event.context or {})
    proc_ctx = cast(JSONDict, context.get("processing") or {})
    attempts = cast(list[JSONDict], proc_ctx["attempts"])
    assert len(attempts) == 1
    assert attempts[0]["error"] == "boom"
    assert event.result == {"payload": {"ok": 1}}


@pytest.mark.asyncio
async def test_retry_exhaustion_marks_flag_and_err() -> None:
    """Cuando todas los intentos fallan con error transitorio, debe retornar Err
    y marcar `retry_exhausted` en el contexto de procesamiento.

    Además, el estado transiciona tempranamente a TEMPORAL_ERROR durante los intentos.
    """
    processor = DummyProcessor()
    # Forzar 3 fallos transitorios (RuntimeError) para agotar los reintentos
    processor._process.side_effect = [
        RuntimeError("boom1"),
        RuntimeError("boom2"),
        RuntimeError("boom3"),
    ]

    usecase = make_usecase_with_processor(processor)
    event = Event(
        id=uuid4(), name="evt", state=EventState.PROCESSING, payload={}, context={}
    )

    result = await usecase.process_with_retries(event)

    # Debe ser Err tras agotar max_attempts
    assert result.is_err()
    err = result.unwrap_err()
    assert err.error == "RUNTIME_FAILED"
    assert "Failed after" in err.detail
    # Metadata debe indicar tipo de error TRANSIENT
    assert err.metadata and err.metadata.get("error_type") == ErrorType.TRANSIENT.value

    # Estado debe haber pasado a TEMPORAL_ERROR en el primer fallo
    assert event.state == EventState.TEMPORAL_ERROR

    # Contexto de procesamiento debe reflejar los intentos y retry_exhausted
    context = cast(JSONDict, event.context or {})
    proc_ctx = cast(JSONDict, context.get("processing") or {})
    attempts = cast(list[JSONDict], proc_ctx.get("attempts") or [])
    assert len(attempts) == usecase.max_attempts
    assert proc_ctx.get("retry_exhausted") is True
    # Último intento debe registrar el error más reciente
    assert attempts[-1]["error"] == "boom3"
