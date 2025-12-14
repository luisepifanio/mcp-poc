from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.respository_event import EventRepository
from app.core.entities import Event
from app.errors import ErrorCatalog, ErrorDetail


class DummyRepo(EventRepository):
    def __init__(self, getmany_ret):
        self._getmany_ret = getmany_ret

    async def delete(self, event: Event, hard: bool = False):
        return Ok(False)

    async def get_by_external_uuid(self, external_uuid):
        return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))

    async def getMany(self, ids: list):
        return self._getmany_ret

    async def saveMany(self, events: list):
        return Ok([])


@pytest.mark.asyncio
async def test_getone_propagates_err_from_getmany():
    err = Err(ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail="boom"))
    repo = DummyRepo(err)

    res = await repo.getOne(uuid4())
    assert isinstance(res, Err)
    assert res.unwrap_err().error == ErrorCatalog.RUNTIME_FAILED.value


@pytest.mark.asyncio
async def test_getone_empty_returns_not_found():
    repo = DummyRepo(Ok([]))
    res = await repo.getOne(uuid4())
    assert isinstance(res, Err)
    assert res.unwrap_err().error == ErrorCatalog.NOT_FOUND.value


@pytest.mark.asyncio
async def test_getone_single_returns_ok():
    ev = Event(name="a")
    repo = DummyRepo(Ok([ev]))
    res = await repo.getOne(ev.id)
    assert isinstance(res, Ok)
    got = res.unwrap()
    assert got.id == ev.id
    assert got.name == ev.name


@pytest.mark.asyncio
async def test_getone_multiple_returns_validation_failed():
    ev1 = Event(name="a")
    ev2 = Event(name="b")
    repo = DummyRepo(Ok([ev1, ev2]))
    res = await repo.getOne(uuid4())
    assert isinstance(res, Err)
    assert res.unwrap_err().error == ErrorCatalog.VALIDATION_FAILED.value


@pytest.mark.asyncio
async def test_getone_error_detail_messages():
    """Assert the exact detail messages produced by getOne for the NOT_FOUND and VALIDATION_FAILED cases."""
    missing_id = uuid4()
    repo_empty = DummyRepo(Ok([]))
    res_empty = await repo_empty.getOne(missing_id)
    assert isinstance(res_empty, Err)
    err_empty = res_empty.unwrap_err()
    assert err_empty.error == ErrorCatalog.NOT_FOUND.value
    assert err_empty.detail == f"Event with id {missing_id} not found."

    ev1 = Event(name="x")
    ev2 = Event(name="y")
    repo_multi = DummyRepo(Ok([ev1, ev2]))
    res_multi = await repo_multi.getOne(missing_id)
    assert isinstance(res_multi, Err)
    err_multi = res_multi.unwrap_err()
    assert err_multi.error == ErrorCatalog.VALIDATION_FAILED.value
    assert (
        err_multi.detail
        == f"Found {2} events for id {missing_id}, please check schema definition."
    )
