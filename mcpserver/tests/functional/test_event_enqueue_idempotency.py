from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import EventState
from app.core.usecases.event_usecases import EnqueueEventUseCase, EventUseCaseInput
from app.errors import ErrorCatalog, ErrorDetail


class InMemorySpyRepo:
    def __init__(self):
        self.storage: dict = {}

    async def get_by_external_uuid(self, external_uuid):
        ev = self.storage.get(str(external_uuid))
        if ev is None:
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))
        return Ok(ev)

    async def getOne(self, id_):
        for ev in self.storage.values():
            if ev.id == id_:
                return Ok(ev)
        return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))

    async def getMany(self, ids):
        found = [ev for ev in self.storage.values() if ev.id in ids]
        if not found:
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))
        return Ok(found)

    async def saveMany(self, events):
        # emulate upsert by external_uuid
        list_of_events = []
        for ev in events:
            key = str(ev.external_uuid) if ev.external_uuid is not None else str(ev.id)
            existing = self.storage.get(key)
            if existing is None:
                # emulate DB assign id and persist
                self.storage[key] = ev
                list_of_events.append(ev)
            else:
                # emulate update: do not change state if existing has progressed
                # but update payload/context/result
                existing.payload = ev.payload
                existing.context = ev.context
                list_of_events.append(existing)
        return Ok(list_of_events)

    async def save(self, event):
        # emulate repository.save which returns a single Event wrapped in Ok
        await self.saveMany([event])
        return Ok(event)


@pytest.mark.asyncio
async def test_enqueue_idempotent_by_external_uuid(mocker, uow_factory):
    # prepare session-like object
    from unittest.mock import AsyncMock, MagicMock

    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    session.rollback = AsyncMock()

    spy = InMemorySpyRepo()

    # Patch the repository used by the UnitOfWork to return our spy
    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyEventRepository",
        return_value=spy,
    )

    external = uuid4()

    async with uow_factory(session) as uow:
        uc = EnqueueEventUseCase(uow)
        inp = EventUseCaseInput(
            name="idemp-test", external_uuid=external, payload={"k": "v"}
        )

        res1 = await uc.execute(inp)
        assert isinstance(res1, Ok)
        out1 = res1.unwrap()

        # call a second time with the same external_uuid
        res2 = await uc.execute(inp)
        assert isinstance(res2, Ok)
        out2 = res2.unwrap()

        # ensure storage has only one entry and both outputs refer to same id
        assert len(spy.storage) == 1
        assert out1.id == out2.id
        assert out1.state == EventState.PENDING
        assert out2.state == EventState.PENDING
