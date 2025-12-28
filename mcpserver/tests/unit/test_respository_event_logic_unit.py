from uuid import UUID, uuid4

import pytest
from result import Err, Ok, Result

from app.core.entities import Event, EventState
from app.core.repository_event import EventRepository
from app.errors import ErrorDetail


class FakeRepo(EventRepository):
    def __init__(self, many_return: Result[list[Event], ErrorDetail]) -> None:
        self._many_return: Result[list[Event], ErrorDetail] = many_return

    async def delete(self, event: Event, hard: bool = False) -> Result[bool, ErrorDetail]:
        return Ok(True)

    async def get_by_external_uuid(
        self, external_uuid: UUID
    ) -> Result[Event, ErrorDetail]:
        return Err(ErrorDetail(error="NOT_FOUND", detail="not"))

    async def getMany(self, ids: list[UUID]) -> Result[list[Event], ErrorDetail]:
        return self._many_return

    async def saveMany(self, events: list[Event]) -> Result[list[Event], ErrorDetail]:
        return self._many_return

    async def save_or_resolve(
        self, events: list[Event]
    ) -> Result[list[Event], ErrorDetail]:
        """Idempotent save - returns saved or existing events."""
        return self._many_return

    async def save_or_resolve_one(self, event: Event) -> Result[Event, ErrorDetail]:
        return Ok(event)


@pytest.mark.asyncio
async def test_getone_success_and_failure_cases() -> None:
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
async def test_save_default_logic() -> None:
    e = Event(name="x", external_uuid=uuid4(), state=EventState.CREATED)
    repo_ok = FakeRepo(Ok([e]))
    res = await repo_ok.save(e)
    assert isinstance(res, Ok)

    repo_err = FakeRepo(Err(ErrorDetail(error="RUNTIME_FAILED", detail="boom")))
    res2 = await repo_err.save(e)
    assert isinstance(res2, Err)
