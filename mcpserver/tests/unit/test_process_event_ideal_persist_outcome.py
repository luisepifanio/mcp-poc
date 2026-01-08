from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.entities import Event, EventState, EventTransition, JSONDict
from app.core.usecases.neo_event_usecase import ProcessEventIdealUseCase


def make_uow_mock() -> MagicMock:
    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock()
    uow.commit = AsyncMock()
    return uow


@pytest.mark.asyncio
async def test_persist_success_processing_to_completed() -> None:
    uow = make_uow_mock()
    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(
        id=uuid4(), name="evt", state=EventState.PROCESSING, payload={}, context={}
    )
    event.result = {"payload": {"ok": True}}

    uow.events.save.return_value = AsyncMock()
    uow.events.save.return_value = uow.events.save.return_value
    # Save returns Ok(event)
    from result import Ok

    uow.events.save.return_value = Ok(event)

    res = await usecase.persist_outcome(event)

    assert res.is_ok()
    persisted = res.unwrap()
    assert persisted.state == EventState.COMPLETED
    uow.events.save.assert_awaited()
    uow.commit.assert_awaited()


@pytest.mark.asyncio
async def test_persist_success_retrying_to_completed() -> None:
    uow = make_uow_mock()
    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(
        id=uuid4(), name="evt", state=EventState.RETRYING, payload={}, context={}
    )
    event.result = {"payload": {"ok": True}}

    from result import Ok

    uow.events.save.return_value = Ok(event)

    res = await usecase.persist_outcome(event)

    assert res.is_ok()
    assert event.state == EventState.COMPLETED


@pytest.mark.asyncio
async def test_persist_pending_callback_no_state_change() -> None:
    uow = make_uow_mock()
    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(
        id=uuid4(), name="evt", state=EventState.RETRYING, payload={}, context={}
    )
    # Set pending callback in processing context
    event.context = {"processing": {"pending_callback": True}}

    from result import Ok

    uow.events.save.return_value = Ok(event)

    res = await usecase.persist_outcome(event)

    assert res.is_ok()
    assert event.state == EventState.RETRYING
    ctx = cast(JSONDict, event.context or {})
    proc = cast(JSONDict, ctx.get("processing") or {})
    assert proc.get("last_activity") is not None


@pytest.mark.asyncio
async def test_persist_retry_exhausted_from_retrying_to_exhausted() -> None:
    uow = make_uow_mock()
    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(
        id=uuid4(), name="evt", state=EventState.TEMPORAL_ERROR, payload={}, context={}
    )
    # Simulate prior transition RETRYING -> TEMPORAL_ERROR
    event.transitions = [
        EventTransition(
            event_id=event.id,
            from_state=EventState.RETRYING,
            to_state=EventState.TEMPORAL_ERROR,
        )
    ]
    event.context = {"processing": {"retry_exhausted": True, "attempts": [{}, {}, {}]}}

    from result import Ok

    uow.events.save.return_value = Ok(event)

    res = await usecase.persist_outcome(event)

    assert res.is_ok()
    assert event.state == EventState.EXHAUSTED
    ctx = cast(JSONDict, event.context or {})
    proc = cast(JSONDict, ctx.get("processing") or {})
    assert proc.get("failed_at") is not None
    assert proc.get("retry_count") == 3


@pytest.mark.asyncio
async def test_persist_retry_exhausted_from_processing_keeps_temporal_error() -> None:
    uow = make_uow_mock()
    usecase = ProcessEventIdealUseCase(uow=uow)
    event = Event(
        id=uuid4(), name="evt", state=EventState.TEMPORAL_ERROR, payload={}, context={}
    )
    # Simulate prior transition PROCESSING -> TEMPORAL_ERROR
    event.transitions = [
        EventTransition(
            event_id=event.id,
            from_state=EventState.PROCESSING,
            to_state=EventState.TEMPORAL_ERROR,
        )
    ]
    event.context = {"processing": {"retry_exhausted": True, "attempts": [{}, {}, {}]}}

    from result import Ok

    uow.events.save.return_value = Ok(event)

    res = await usecase.persist_outcome(event)

    assert res.is_ok()
    assert event.state == EventState.TEMPORAL_ERROR
