from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import Event, EventState
from app.core.usecases.neo_event_usecase import ProcessEventIdealUseCase
from app.errors import ErrorCatalog, ErrorDetail


@pytest.mark.asyncio
async def test_pending_transitions_to_processing_and_persists() -> None:
    # Arrange
    event = Event(id=uuid4(), name="e1", state=EventState.PENDING, payload={}, context={})
    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock(return_value=Ok(event))
    uow.commit = AsyncMock(return_value=None)

    usecase = ProcessEventIdealUseCase(uow)

    # Act
    result = await usecase.validate_and_lock(event)

    # Assert
    assert result.is_ok()
    saved = result.unwrap()
    assert saved.state == EventState.PROCESSING
    assert isinstance(saved.context, dict)
    proc = saved.context.get("processing") if saved.context is not None else None
    assert isinstance(proc, dict)
    assert "started_at" in proc and "last_activity" in proc
    uow.events.save.assert_awaited_once_with(event)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_temporal_error_transitions_to_retrying_and_persists() -> None:
    # Arrange
    event = Event(
        id=uuid4(), name="e2", state=EventState.TEMPORAL_ERROR, payload={}, context={}
    )
    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock(return_value=Ok(event))
    uow.commit = AsyncMock(return_value=None)

    usecase = ProcessEventIdealUseCase(uow)

    # Act
    result = await usecase.validate_and_lock(event)

    # Assert
    assert result.is_ok()
    saved = result.unwrap()
    assert saved.state == EventState.RETRYING
    proc = saved.context.get("processing") if saved.context is not None else None
    assert isinstance(proc, dict)
    assert proc.get("pending_callback") is False
    uow.events.save.assert_awaited_once_with(event)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_state_returns_err_without_persist() -> None:
    # Arrange
    event = Event(id=uuid4(), name="e3", state=EventState.CREATED, payload={}, context={})
    uow = MagicMock()
    uow.events = MagicMock()
    uow.events.save = AsyncMock()
    uow.commit = AsyncMock()
    usecase = ProcessEventIdealUseCase(uow)

    # Act
    result = await usecase.validate_and_lock(event)

    # Assert
    assert result.is_err()
    err = result.unwrap_err()
    assert isinstance(err, ErrorDetail)
    assert err.error == ErrorCatalog.VALIDATION_FAILED.value
    uow.events.save.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.asyncio
async def test_save_error_is_propagated() -> None:
    # Arrange
    event = Event(id=uuid4(), name="e4", state=EventState.PENDING, payload={}, context={})
    uow = MagicMock()
    uow.events = MagicMock()
    save_err = ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail="db error")
    uow.events.save = AsyncMock(return_value=Err(save_err))
    uow.commit = AsyncMock()
    usecase = ProcessEventIdealUseCase(uow)

    # Act
    result = await usecase.validate_and_lock(event)

    # Assert
    assert result.is_err()
    err = result.unwrap_err()
    assert err.detail == "db error"
    uow.events.save.assert_awaited_once_with(event)
    uow.commit.assert_not_called()
