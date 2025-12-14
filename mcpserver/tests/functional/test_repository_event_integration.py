from uuid import uuid4

import pytest
from result import Ok

from app.core.entities import Event, EventState
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository


@pytest.mark.asyncio
async def test_save_or_resolve_integration_conflict_resolution(async_session_local):
    """Integration: persist an event, then attempt to save another with same external_uuid
    and verify repository returns the canonical existing event on conflict using save_or_resolve.
    """
    AsyncSessionLocal = async_session_local

    async with AsyncSessionLocal() as session:
        repo = AsyncSQLAlchemyEventRepository(session)

        original = Event(
            name="orig", external_uuid=uuid4(), payload={"x": 1}, state=EventState.PENDING
        )
        saved_res = await repo.save(original)
        assert isinstance(saved_res, Ok)
        saved = saved_res.unwrap()
        # Persist the insert to the DB so subsequent conflicting inserts from
        # the same or other sessions can be resolved. The repository does not
        # perform commits (UoW is responsible), so commit explicitly here.
        await session.commit()

        # Create a new Event with same external_uuid
        new_ev = Event(
            name="new",
            external_uuid=saved.external_uuid,
            payload={"y": 2},
            state=EventState.CREATED,
        )

        # Attempt to save_or_resolve; should return the existing canonical event
        res = await repo.save_or_resolve([new_ev])
        assert isinstance(res, Ok)
        lst = res.unwrap()
        assert len(lst) == 1
        found = lst[0]
        assert found.id == saved.id
