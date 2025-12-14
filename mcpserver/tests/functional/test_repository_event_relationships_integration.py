import pytest
from uuid import uuid4

from result import Ok

from app.core.entities import Event, EventTransition, EventState
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository


@pytest.mark.asyncio
async def test_saveMany_does_not_overwrite_relationship_internals(async_session_local):
    """Regression test: ensure saveMany does not overwrite relationship internals
    (no direct __dict__ assignment that would break SQLAlchemy instrumentation).
    """
    AsyncSessionLocal = async_session_local

    async with AsyncSessionLocal() as session:
        repo = AsyncSQLAlchemyEventRepository(session)

        # Original event with a pre-populated transition
        original = Event(
            name="orig",
            external_uuid=uuid4(),
            payload={"x": 1},
            state=EventState.PENDING,
        )
        original.transitions = [
            EventTransition(from_state=EventState.PENDING, to_state=EventState.PROCESSING)
        ]

        saved_res = await repo.saveMany([original])
        assert isinstance(saved_res, Ok)
        saved_list = saved_res.unwrap()
        assert len(saved_list) == 1
        saved = saved_list[0]

        # Persist to DB so a subsequent conflicting insert will raise a uniqueness error
        await session.commit()

        # Create another event with same external_uuid to trigger conflict resolution
        new_ev = Event(
            name="new",
            external_uuid=saved.external_uuid,
            payload={"y": 2},
            state=EventState.CREATED,
        )

        res = await repo.saveMany([new_ev])
        assert isinstance(res, Ok)
        resolved_list = res.unwrap()
        assert len(resolved_list) == 1
        resolved = resolved_list[0]

        # The repository must not have assigned a plain list into SQLAlchemy internals.
        transitions_attr = resolved.__dict__.get("transitions", None)

        # Acceptable states:
        # - None (not loaded)
        # - an instrumented collection (has attribute '_sa_adapter')
        # - any non-plain-list object
        assert (
            transitions_attr is None
            or hasattr(transitions_attr, "_sa_adapter")
            or not isinstance(transitions_attr, list)
        )
