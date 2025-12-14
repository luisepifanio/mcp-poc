import json
from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import EventState
from app.core.usecases.event_usecases import EnqueueEventUseCase, EventUseCaseInput
from app.errors import ErrorCatalog, ErrorDetail


class ConflictSpyRepo:
    """Repo that simulates a uniqueness violation on save but has the existing event available."""

    def __init__(self, existing_event):
        self.existing = existing_event

    async def get_by_external_uuid(self, external_uuid):
        if self.existing is None:
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))
        return Ok(self.existing)

    async def getOne(self, id_):
        if self.existing is None:
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))
        return Ok(self.existing)

    async def getMany(self, ids):
        if self.existing is None:
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))
        return Ok([self.existing])

    async def saveMany(self, events):
        return Err(
            ErrorDetail(
                error=ErrorCatalog.RUNTIME_FAILED.value, detail="UNIQUE constraint failed"
            )
        )

    async def save_or_resolve(self, events):
        # Idempotent: return existing event if conflict occurs
        if self.existing is not None:
            return Ok([self.existing])
        return Ok(events)

    async def save(self, event):
        return await self.saveMany([event])


@pytest.mark.asyncio
async def test_enqueue_rejects_invalid_initial_state(mocker, uow_factory):
    from unittest.mock import AsyncMock, MagicMock

    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    session.rollback = AsyncMock()

    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyEventRepository",
        return_value=ConflictSpyRepo(None),
    )
    async with uow_factory(session) as uow:
        uc = EnqueueEventUseCase(uow)
        inp = EventUseCaseInput(
            name="badstate",
            external_uuid=uuid4(),
            payload={},
            state=EventState.PROCESSING,
        )
        res = await uc.execute(inp)
        assert isinstance(res, Err)
        assert res.unwrap_err().error == ErrorCatalog.VALIDATION_FAILED.value


@pytest.mark.asyncio
async def test_payload_normalization_before_save(mocker, uow_factory):
    from unittest.mock import AsyncMock, MagicMock

    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    session.rollback = AsyncMock()

    # Spy repo that records saved events
    class SpyRepo:
        def __init__(self):
            self.saved = None

        async def get_by_external_uuid(self, external_uuid):
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))

        async def getOne(self, id_):
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))

        async def getMany(self, ids):
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="no"))

        async def saveMany(self, events):
            self.saved = events
            return Ok(events)

        async def save_or_resolve(self, events):
            # Idempotent: just save for this simple spy
            self.saved = events
            return Ok(events)

        async def save(self, event):
            # return a single Event wrapped in Ok to emulate repository.save behavior
            await self.saveMany([event])
            return Ok(event)

    spy = SpyRepo()

    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyEventRepository",
        return_value=spy,
    )
    external = uuid4()
    async with uow_factory(session) as uow:
        uc = EnqueueEventUseCase(uow)
        payload = {"b": 1, "a": 2}
        inp = EventUseCaseInput(name="normalize", external_uuid=external, payload=payload)
        res = await uc.execute(inp)
        assert isinstance(res, Ok)
        # confirm saved payload normalized deterministically
        saved = spy.saved[0]
        assert json.dumps(saved.payload, sort_keys=True) == json.dumps(
            payload, sort_keys=True
        )


@pytest.mark.asyncio
async def test_integrity_conflict_returns_existing(mocker, uow_factory):
    from unittest.mock import AsyncMock, MagicMock

    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    session.rollback = AsyncMock()

    # build existing event-like object
    from app.core.entities import Event

    existing = Event(name="existing", external_uuid=uuid4(), payload={"k": "v"})

    conflict_repo = ConflictSpyRepo(existing)

    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyEventRepository",
        return_value=conflict_repo,
    )

    async with uow_factory(session) as uow:
        uc = EnqueueEventUseCase(uow)
        inp = EventUseCaseInput(
            name="new-one", external_uuid=existing.external_uuid, payload={}
        )
        res = await uc.execute(inp)
        assert isinstance(res, Ok)
        out = res.unwrap()
        assert out.external_uuid == existing.external_uuid
