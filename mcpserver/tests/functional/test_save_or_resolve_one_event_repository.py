import logging

# Get a logger for this module
from collections.abc import AsyncGenerator, Callable
from typing import AsyncContextManager, cast
from uuid import UUID

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

    events: list[Event] = [
        Event(
            name="RegisterEvent",
            external_uuid=UUID("5a3b7e2c-1d9f-4c8e-9b2a-6f1e8d4c3b7a"),
            state=EventState.PROCESSING,
        ),
    ]

    tx1: list[EventTransition] = [
        EventTransition(
            event_id=events[0].id,
            from_state=EventState.CREATED,
            to_state=EventState.PENDING,
        ),
        EventTransition(
            event_id=events[0].id,
            from_state=EventState.PENDING,
            to_state=EventState.PROCESSING,
        ),
    ]
    events[0].transitions += tx1

    # Insert events into the database, prior to yielding them
    async with dbsession as session:
        session.add_all(events)
        await session.commit()
        await session.flush()

        await session.refresh(events[0])

    yield events
    logger.debug("Tearing down events after test function...")

    query = delete(Event).where(col(Event.id).in_([event.id for event in events]))
    async with dbsession as session:
        await session.execute(query)
        await session.commit()


@pytest.mark.asyncio
async def test_save_or_resolve_one(
    uow_factory: Callable[[], AsyncContextManager[UnitOfWork]],
    events_in_db: list[Event],
) -> None:
    async with uow_factory() as uow:
        repo: AsyncSQLAlchemyEventRepository = cast(
            AsyncSQLAlchemyEventRepository, uow.events
        )
        event: Event = events_in_db[0].model_copy(deep=True)

        result = await repo.save_or_resolve_one(event)

        assert isinstance(result, Ok)
        event = result.unwrap()
        assert event.id == events_in_db[0].id
        assert event.external_uuid == events_in_db[0].external_uuid
