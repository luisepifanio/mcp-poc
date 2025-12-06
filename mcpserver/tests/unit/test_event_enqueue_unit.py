from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import Event, EventState
from app.core.usecases.event_usecases import (
    LOOKUP_EVENT_NAMES,
    EnqueueEventUseCase,
    EventUseCaseInput,
)
from app.errors import ErrorCatalog, ErrorDetail


class FakeRepo:
    def __init__(self, get_by_external_ret, getone_ret, savemany_ret=None):
        self._get_by_external_ret = get_by_external_ret
        self._getone_ret = getone_ret
        self._savemany_ret = savemany_ret or Ok([])
        self.saved = None

    async def get_by_external_uuid(self, external_uuid):
        return self._get_by_external_ret

    async def getMany(self, ids: list):
        return self._getone_ret if isinstance(self._getone_ret, Ok) else self._getone_ret

    async def getOne(self, id_):
        return self._getone_ret

    async def saveMany(self, events: list):
        self.saved = events
        return self._savemany_ret

    async def save(self, event):
        return await self.saveMany([event])


class FakeUoW:
    def __init__(self, repo):
        self.events = repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_enqueue_returns_existing_by_external_uuid():
    ev = Event(name="e", external_uuid=uuid4(), state=EventState.CREATED)
    repo = FakeRepo(
        Ok(ev), Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))
    )
    uow = FakeUoW(repo)
    uc = EnqueueEventUseCase(uow)

    inp = EventUseCaseInput(
        name=ev.name, external_uuid=ev.external_uuid, id=ev.id, payload={"x": 1}
    )
    res = await uc.execute(inp)

    assert isinstance(res, Ok)
    out = res.unwrap()
    assert out.id == ev.id
    assert out.external_uuid == ev.external_uuid


@pytest.mark.asyncio
async def test_enqueue_returns_existing_by_id():
    ev = Event(name="e", external_uuid=uuid4(), state=EventState.CREATED)
    repo = FakeRepo(
        Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")), Ok(ev)
    )
    uow = FakeUoW(repo)
    uc = EnqueueEventUseCase(uow)

    inp = EventUseCaseInput(name=ev.name, external_uuid=None, id=ev.id, payload={"x": 1})
    res = await uc.execute(inp)

    assert isinstance(res, Ok)
    out = res.unwrap()
    assert out.id == ev.id


@pytest.mark.asyncio
async def test_enqueue_creates_new_and_saves():
    # Both lookups return NOT_FOUND -> should create and save with PENDING state
    repo = FakeRepo(
        Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
        Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
    )
    # Save should return the saved event wrapped in Ok
    saved_event = Event(name="created", external_uuid=uuid4(), state=EventState.PENDING)
    repo._savemany_ret = Ok([saved_event])

    uow = FakeUoW(repo)
    uc = EnqueueEventUseCase(uow)

    inp = EventUseCaseInput(name="created", external_uuid=None, payload={"created": True})
    res = await uc.execute(inp)

    assert isinstance(res, Ok)
    out = res.unwrap()
    # save should have been called and returned the saved event
    assert out.name == saved_event.name
    assert out.state == EventState.PENDING


@pytest.mark.asyncio
async def test_enqueue_lookup_event_returns_not_found_error():
    # When name is in LOOKUP_EVENT_NAMES and getOne returns NOT_FOUND -> propagate Err
    name = next(iter(LOOKUP_EVENT_NAMES))
    repo = FakeRepo(
        Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
        Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
    )
    uow = FakeUoW(repo)
    uc = EnqueueEventUseCase(uow)

    inp = EventUseCaseInput(name=name, external_uuid=None, payload={"lookup": True})
    res = await uc.execute(inp)

    assert isinstance(res, Err)
    err = res.unwrap_err()
    assert err.error == ErrorCatalog.NOT_FOUND.value
