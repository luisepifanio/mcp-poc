import logging

# Get a logger for this module
from collections.abc import AsyncGenerator, Callable
from typing import AsyncContextManager, cast
from uuid import UUID, uuid4

import pytest
from result import Ok
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, delete

from app.core.entities import Event, EventState, EventTransition
from app.core.unit_of_work import UnitOfWork
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository

logger = logging.getLogger(__name__)


@pytest.fixture
async def events_in_db(dbsession: AsyncSession) -> AsyncGenerator[list[Event], None]:
    logger.debug("Setting up events to be created...")

    events: list[Event] = []

    # Original event with a pre-populated transition
    original = Event(
        name="orig",
        external_uuid=uuid4(),
        payload={"x": 1},
        state=EventState.TEMPORAL_ERROR,
    )

    original.transitions = [
        EventTransition(
            event_id=original.id,
            from_state=EventState.CREATED,
            to_state=EventState.PENDING,
        ),
        EventTransition(
            event_id=original.id,
            from_state=EventState.PENDING,
            to_state=EventState.PROCESSING,
        ),
        EventTransition(
            event_id=original.id,
            from_state=EventState.PROCESSING,
            to_state=EventState.TEMPORAL_ERROR,
        ),
    ]

    events.append(original)

    # Insert events into the database, prior to yielding them
    async with dbsession as session:
        session.add_all(events)
        await session.commit()
        await session.flush()
        for evt in events:
            await session.refresh(evt)

    yield events
    logger.debug("Tearing down events after test function...")

    query = delete(Event).where(col(Event.id).in_([event.id for event in events]))
    async with dbsession as session:
        await session.execute(query)
        await session.commit()


@pytest.mark.asyncio
async def test_save_or_resolve_does_not_overwrite_relationship_internals(
    uow_factory: Callable[[], AsyncContextManager[UnitOfWork]],
    events_in_db: list[Event],
) -> None:
    """Regression test: ensure save_or_resolve does not overwrite relationship internals
    (no direct __dict__ assignment that would break SQLAlchemy instrumentation).
    """
    async with uow_factory() as uow:
        repo: AsyncSQLAlchemyEventRepository = cast(
            AsyncSQLAlchemyEventRepository, uow.events
        )
        saved: Event = events_in_db[0]  # .model_copy(deep=True)

        # Create another event with same external_uuid to trigger conflict resolution
        new_ev = Event(
            name="new",
            external_uuid=saved.external_uuid,
            payload={"y": 2},
            state=EventState.CREATED,
        )

        res = await repo.save_or_resolve([new_ev])
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
