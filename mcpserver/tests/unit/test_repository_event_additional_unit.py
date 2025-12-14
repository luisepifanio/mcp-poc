from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from result import Err, Ok
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventState
from app.errors import ErrorCatalog, ErrorDetail
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository


@pytest.mark.asyncio
async def test_saveMany_success_sets_transitions_and_returns_events():
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
async def test_save_or_resolve_conflict_resolves_existing(mocker):
    """Test that save_or_resolve uses savepoints and resolves conflicts."""
    session = MagicMock(spec=AsyncSession)

    # flush will raise IntegrityError to trigger conflict branch
    def _raise(*_args, **_kwargs):
        raise IntegrityError("stmt", {}, Exception("orig"))

    session.flush = AsyncMock(side_effect=_raise)
    session.add = MagicMock()

    # Mock begin_nested to return an async context manager that raises on flush
    nested_ctx = MagicMock()
    nested_ctx.__aenter__ = AsyncMock(return_value=None)
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_ctx)

    repo = AsyncSQLAlchemyEventRepository(session)

    # the resolved existing event returned by FastCRUD.get
    existing = Event(name="existing", external_uuid=uuid4(), state=EventState.PENDING)

    # Patch FastCRUD.get to return the existing event
    mocker.patch("fastcrud.FastCRUD.get", return_value=existing)

    ev = Event(
        name="conflict", external_uuid=existing.external_uuid, state=EventState.CREATED
    )

    res = await repo.save_or_resolve([ev])
    assert isinstance(res, Ok)
    lst = res.unwrap()
    assert len(lst) == 1
    assert lst[0].external_uuid == existing.external_uuid


@pytest.mark.asyncio
async def test_save_or_resolve_conflict_unresolved_returns_err(mocker):
    """Test that save_or_resolve returns error when conflict cannot be resolved."""
    session = MagicMock(spec=AsyncSession)

    def _raise(*_args, **_kwargs):
        raise IntegrityError("stmt", {}, Exception("orig"))

    session.flush = AsyncMock(side_effect=_raise)
    session.add = MagicMock()

    # Mock begin_nested to return an async context manager
    nested_ctx = MagicMock()
    nested_ctx.__aenter__ = AsyncMock(return_value=None)
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_ctx)

    repo = AsyncSQLAlchemyEventRepository(session)

    # Patch FastCRUD.get to return None (can't resolve existing)
    mocker.patch("fastcrud.FastCRUD.get", return_value=None)

    ev = Event(name="conflict", external_uuid=uuid4(), state=EventState.CREATED)

    res = await repo.save_or_resolve([ev])
    assert isinstance(res, Err)
    err = res.unwrap_err()
    assert err.error == ErrorCatalog.RUNTIME_FAILED.value
    assert "Conflict detected" in err.detail


@pytest.mark.asyncio
async def test_delete_validation_error_no_id():
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
async def test_delete_not_found_returns_false(mocker):
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
async def test_getMany_returns_list(mocker):
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
