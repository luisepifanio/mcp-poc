from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from result import Err, Ok
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventState
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository


@pytest.mark.asyncio
async def test_get_by_external_uuid_success(mocker):
    session = MagicMock(spec=AsyncSession)
    # Provide common async methods used in repositories to avoid attribute errors
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    repo = AsyncSQLAlchemyEventRepository(session)

    ev = Event(name="e", external_uuid=uuid4(), state=EventState.CREATED)

    # Patch FastCRUD.get to return the Event instance
    mocker.patch("fastcrud.FastCRUD.get", return_value=ev)

    assert ev.external_uuid is not None

    result = await repo.get_by_external_uuid(ev.external_uuid)

    assert isinstance(result, Ok)
    fetched = result.unwrap()
    assert isinstance(fetched, Event)
    assert fetched.external_uuid == ev.external_uuid


@pytest.mark.asyncio
async def test_get_by_external_uuid_not_found(mocker):
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    repo = AsyncSQLAlchemyEventRepository(session)

    missing = uuid4()
    # Patch FastCRUD.get to return None (not found)
    mocker.patch("fastcrud.FastCRUD.get", return_value=None)

    result = await repo.get_by_external_uuid(missing)

    assert isinstance(result, Err)
    err = result.unwrap_err()
    assert err.error == "NOT_FOUND"
    assert str(missing) in err.detail


@pytest.mark.asyncio
async def test_get_by_external_uuid_runtime_error(mocker):
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    repo = AsyncSQLAlchemyEventRepository(session)

    target = uuid4()
    # Simulate FastCRUD.get raising an exception
    mocker.patch("fastcrud.FastCRUD.get", side_effect=ValueError("boom"))

    result = await repo.get_by_external_uuid(target)

    assert isinstance(result, Err)
    err = result.unwrap_err()
    assert err.error == "RUNTIME_FAILED"
    assert "boom" in err.detail
