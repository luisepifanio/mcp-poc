from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from result import Ok
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventState, EventTransition
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository


@pytest.mark.asyncio
async def test_saveMany_with_preloaded_transitions(_mocker):
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.add = MagicMock()

    repo = AsyncSQLAlchemyEventRepository(session)

    ev = Event(name="with-trans", external_uuid=uuid4(), state=EventState.CREATED)
    # create a preloaded transition and attach directly to __dict__ to avoid lazy-loading
    t = EventTransition(
        from_state=EventState.CREATED, to_state=EventState.PENDING, event_id=ev.id
    )
    ev.__dict__["transitions"] = [t]

    res = await repo.saveMany([ev])
    assert isinstance(res, Ok)
    lst = res.unwrap()
    assert len(lst) == 1
    returned = lst[0]
    # transitions should remain attached
    assert isinstance(returned.__dict__.get("transitions"), list)
    assert len(returned.__dict__["transitions"]) == 1


@pytest.mark.asyncio
async def test_saveMany_integrity_rollback_raises_but_resolution_continues(mocker):
    session = MagicMock(spec=AsyncSession)

    def _raise(*_args, **_kwargs):
        raise IntegrityError("stmt", {}, Exception("orig"))

    # flush raises IntegrityError, rollback raises Exception to hit inner except
    session.flush = AsyncMock(side_effect=_raise)

    def _rb_raise(*_args, **_kwargs):
        raise RuntimeError("rollback failed")

    session.rollback = MagicMock(side_effect=_rb_raise)
    session.add = MagicMock()

    repo = AsyncSQLAlchemyEventRepository(session)

    existing = Event(name="existing", external_uuid=uuid4(), state=EventState.PENDING)
    mocker.patch("fastcrud.FastCRUD.get", return_value=existing)

    ev = Event(
        name="conflict", external_uuid=existing.external_uuid, state=EventState.CREATED
    )

    res = await repo.saveMany([ev])
    assert isinstance(res, Ok)
    assert res.unwrap()[0].external_uuid == existing.external_uuid


@pytest.mark.asyncio
async def test_saveMany_conflict_uses_id_lookup_when_no_external_uuid(mocker):
    session = MagicMock(spec=AsyncSession)

    def _raise(*_args, **_kwargs):
        raise IntegrityError("stmt", {}, Exception("orig"))

    session.flush = AsyncMock(side_effect=_raise)
    session.rollback = AsyncMock()
    session.add = MagicMock()

    repo = AsyncSQLAlchemyEventRepository(session)

    existing = Event(name="existing", external_uuid=None, state=EventState.PENDING)

    # patch FastCRUD.get to return None for external_uuid lookup then existing for id lookup
    def fake_get(_session_arg, **_kwargs):
        if _kwargs.get("external_uuid") is not None:
            return None
        if _kwargs.get("id") is not None:
            return existing
        return None

    mocker.patch("fastcrud.FastCRUD.get", side_effect=fake_get)

    ev = Event(name="conflict", external_uuid=None, state=EventState.CREATED)
    ev.id = uuid4()

    res = await repo.saveMany([ev])
    assert isinstance(res, Ok)
    assert res.unwrap()[0] is existing


@pytest.mark.asyncio
async def test_delete_hard_calls_db_delete(mocker):
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repo = AsyncSQLAlchemyEventRepository(session)

    ev = Event(name="h", external_uuid=None, state=EventState.CREATED)
    ev.id = uuid4()

    # patch getOne to return the event
    mocker.patch.object(repo, "getOne", AsyncMock(return_value=Ok(ev)))
    # patch db_delete to be awaited
    mocker.patch.object(repo.event_crud, "db_delete", AsyncMock())

    res = await repo.delete(ev, hard=True)
    assert isinstance(res, Ok)
    assert res.unwrap() is True
    repo.event_crud.db_delete.assert_awaited()


@pytest.mark.asyncio
async def test_getMany_no_data_returns_empty(mocker):
    session = MagicMock(spec=AsyncSession)
    repo = AsyncSQLAlchemyEventRepository(session)

    mocker.patch("fastcrud.FastCRUD.get_multi", return_value={})

    res = await repo.getMany([uuid4(), uuid4()])
    assert isinstance(res, Ok)
    assert res.unwrap() == []
