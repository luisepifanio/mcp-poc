from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from result import Err, Ok
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventState
from app.errors import ErrorCatalog, ErrorDetail
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository


@pytest.mark.asyncio
async def test_saveMany_success_sets_transitions_and_returns_events() -> None:
    # Configure mock session with all required async methods
    session = MagicMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    # Mock execute for eager loading (returns the same events)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    repo = AsyncSQLAlchemyEventRepository(session)

    ev = Event(name="ok", external_uuid=uuid4(), state=EventState.CREATED)

    res = await repo.saveMany([ev])
    assert isinstance(res, Ok)
    lst = res.unwrap()
    assert isinstance(lst, list)
    assert len(lst) == 1
    returned = lst[0]
    # transitions should be accessible (set via instrumented assignment or getattr)
    transitions = getattr(returned, "transitions", None)
    assert transitions is not None
    assert isinstance(transitions, list)


@pytest.mark.asyncio
async def test_delete_validation_error_no_id() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repo = AsyncSQLAlchemyEventRepository(session)

    ev = Event(name="noid", external_uuid=None, state=EventState.CREATED)
    # ensure id is None
    ev.id = None

    res = await repo.delete(ev)
    assert isinstance(res, Err)
    err = res.unwrap_err()
    assert err.error == ErrorCatalog.VALIDATION_FAILED.value


@pytest.mark.asyncio
async def test_delete_not_found_returns_false(mocker: MockerFixture) -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.add = MagicMock()
    repo = AsyncSQLAlchemyEventRepository(session)

    ev = Event(name="todelete", external_uuid=None, state=EventState.CREATED)
    ev.id = uuid4()

    # patch repo.getOne to return Err(NOT_FOUND)
    mocker.patch.object(
        repo,
        "getOne",
        AsyncMock(
            return_value=Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))
        ),
    )

    res = await repo.delete(ev)
    assert isinstance(res, Ok)
    assert res.unwrap() is False


@pytest.mark.asyncio
async def test_getMany_returns_list(mocker: MockerFixture) -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repo = AsyncSQLAlchemyEventRepository(session)

    ev1 = Event(name="a", external_uuid=uuid4(), state=EventState.CREATED)
    ev2 = Event(name="b", external_uuid=uuid4(), state=EventState.CREATED)

    # Patch FastCRUD.get_multi to return expected structure
    mocker.patch(
        "fastcrud.FastCRUD.get_multi", return_value={"data": [ev1, ev2], "total_count": 2}
    )

    res = await repo.getMany([ev1.id, ev2.id])
    assert isinstance(res, Ok)
    lst = res.unwrap()
    assert isinstance(lst, list)
    assert len(lst) == 2
