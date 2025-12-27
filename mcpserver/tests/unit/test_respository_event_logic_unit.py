from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import Event, EventState
from app.core.respository_event import EventRepository
from app.errors import ErrorDetail


class FakeRepo(EventRepository):
    def __init__(self, many_return):
        self._many_return = many_return

    async def delete(self, event: Event, hard: bool = False):
        return Ok(True)

    async def get_by_external_uuid(self, external_uuid):
        return Err(ErrorDetail(error="NOT_FOUND", detail="not"))

    async def getMany(self, ids: list):
        return self._many_return

    async def saveMany(self, events: list):
        return self._many_return

    async def save_or_resolve(self, events: list):
        """Idempotent save - returns saved or existing events."""
        return self._many_return

    async def save_or_resolve_one(self, event: Event) -> Ok[Event] | Err[ErrorDetail]:
        return Ok(event)


@pytest.mark.asyncio
async def test_getone_success_and_failure_cases():
    e = Event(name="x", external_uuid=uuid4(), state=EventState.CREATED)
    # success case: getMany returns exactly one
    repo_ok = FakeRepo(Ok([e]))
    res = await repo_ok.getOne(e.id)
    assert isinstance(res, Ok)
    assert res.unwrap() is e

    # not found: empty list -> Err
    repo_empty = FakeRepo(Ok([]))
    res2 = await repo_empty.getOne(e.id)
    assert isinstance(res2, Err)

    # multiple found -> validation error
    repo_many = FakeRepo(Ok([e, e]))
    res3 = await repo_many.getOne(e.id)
    assert isinstance(res3, Err)


@pytest.mark.asyncio
async def test_save_default_logic():
    e = Event(name="x", external_uuid=uuid4(), state=EventState.CREATED)
    repo_ok = FakeRepo(Ok([e]))
    res = await repo_ok.save(e)
    assert isinstance(res, Ok)

    repo_err = FakeRepo(Err(ErrorDetail(error="RUNTIME_FAILED", detail="boom")))
    res2 = await repo_err.save(e)
    assert isinstance(res2, Err)
