from unittest.mock import AsyncMock, MagicMock

import pytest
from result import Err, Ok

from app.core.entities import EventState
from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseInput,
    EnqueueEventUseCase,
)
from app.errors import ErrorCatalog, ErrorDetail


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
        # emulate DB assigning PENDING state already done by use case
        self.saved = events
        return Ok(events)

    async def save_or_resolve(self, events):
        # Idempotent insert: same behavior as saveMany for this simple spy
        self.saved = events
        return Ok(events)

    async def save(self, event):
        # emulate repository.save: persist and return single Event wrapped in Ok
        await self.saveMany([event])
        return Ok(event)


@pytest.mark.asyncio
async def test_enqueue_with_real_uow_patches_repo(mocker, uow_factory):
    # Prepare a fake AsyncSession similar to other tests
    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    session.rollback = AsyncMock()

    spy = SpyRepo()

    # Patch AsyncSQLAlchemyEventRepository used by the UnitOfWork to return our spy
    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyEventRepository",
        return_value=spy,
    )

    async with uow_factory(session) as uow:
        uc = EnqueueEventUseCase(uow)
        inp = EnqueuedEventUseCaseInput(
            name="functional-test", external_uuid=None, payload={"functional": True}
        )
        res = await uc.execute(inp)

        assert isinstance(res, Ok)
        out = res.unwrap()
        # ensure the spy repo saved something
        assert spy.saved is not None
        assert out.name == "functional-test"
        assert out.state == EventState.PENDING
