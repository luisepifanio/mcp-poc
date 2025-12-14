from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import Event, EventState
from app.core.usecases.event_usecases import EnqueueEventUseCase, EventUseCaseInput, transition_event
from app.errors import ErrorCatalog, ErrorDetail


class SimpleRepo:
    def __init__(self, get_by_external_ret, getone_ret, savemany_ret=None):
        self._get_by_external_ret = get_by_external_ret
        self._getone_ret = getone_ret
        self._savemany_ret = savemany_ret or Ok([])

    async def get_by_external_uuid(self, external_uuid):
        return self._get_by_external_ret

    async def getOne(self, id_):
        return self._getone_ret

    async def saveMany(self, events: list):
        return self._savemany_ret

    async def save(self, event):
        return await self.saveMany([event])


class SimpleUoW:
    def __init__(self, repo):
        self.events = repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_execute_returns_validation_err_for_malformed_input():
    # Pass a plain dict instead of EventUseCaseInput to trigger RootModel validation
    repo = SimpleRepo(Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
                      Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")))
    uow = SimpleUoW(repo)
    uc = EnqueueEventUseCase(uow)

    bad_input = {"name": "ok", "payload": "this-should-be-a-dict"}
    res = await uc.execute(bad_input)  # type: ignore[arg-type]

    assert isinstance(res, Err)
    assert res.unwrap_err().error == ErrorCatalog.VALIDATION_FAILED.value


@pytest.mark.asyncio
async def test_execute_propagates_save_runtime_error():
    # Save returns a runtime Err -> use case should propagate it
    err = ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail="db down")
    repo = SimpleRepo(Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
                      Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
                      savemany_ret=Err(err))
    uow = SimpleUoW(repo)
    uc = EnqueueEventUseCase(uow)

    inp = EventUseCaseInput(name="rtex", external_uuid=None, payload={})
    res = await uc.execute(inp)

    assert isinstance(res, Err)
    assert res.unwrap_err().error == ErrorCatalog.RUNTIME_FAILED.value


@pytest.mark.asyncio
async def test_execute_handles_save_returning_multiple_events_as_error():
    # If repository returns multiple events for single save -> runtime error
    ev1 = Event(name="a", external_uuid=uuid4(), state=EventState.PENDING)
    ev2 = Event(name="b", external_uuid=uuid4(), state=EventState.PENDING)
    repo = SimpleRepo(Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
                      Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
                      savemany_ret=Ok([ev1, ev2]))
    uow = SimpleUoW(repo)
    uc = EnqueueEventUseCase(uow)

    inp = EventUseCaseInput(name="multi", external_uuid=None, payload={})
    res = await uc.execute(inp)

    assert isinstance(res, Err)
    assert res.unwrap_err().error == ErrorCatalog.RUNTIME_FAILED.value


def test_transition_event_invalid():
    # Transition from COMPLETED to PENDING is invalid
    ev = Event(name="x", external_uuid=uuid4(), state=EventState.COMPLETED)
    res = transition_event(ev, EventState.PENDING)
    assert isinstance(res, Err)
    assert res.unwrap_err().error == ErrorCatalog.VALIDATION_FAILED.value


@pytest.mark.asyncio
async def test_getone_err_non_not_found_returns_runtime_failed_case():
    # get_by_external_uuid not found, but getOne returns Err with a non-NOT_FOUND error
    repo = SimpleRepo(Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no")),
                      Err(ErrorDetail(error=ErrorCatalog.RUNTIME_FAILED.value, detail="weird")))
    uow = SimpleUoW(repo)
    uc = EnqueueEventUseCase(uow)

    inp = EventUseCaseInput(name="normal", external_uuid=None, id=uuid4(), payload={})
    res = await uc.execute(inp)

    assert isinstance(res, Err)
    assert res.unwrap_err().error == ErrorCatalog.RUNTIME_FAILED.value
