import logging

# Get a logger for this module
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from result import Ok
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, delete

from app.core.entities import Event, EventState
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository

logger = logging.getLogger(__name__)


@pytest.fixture
async def events_to_create(dbsession: AsyncSession) -> AsyncGenerator[list[Event], None]:
    logger.debug("Setting up events to be created...")

    events: list[Event] = [
        Event(name="e1", external_uuid=None, state=EventState.CREATED),
        Event(name="e2", external_uuid=uuid4(), state=EventState.CREATED),
    ]

    yield events
    logger.debug("Tearing down events after test function...")

    query = delete(Event).where(col(Event.id).in_([event.id for event in events]))
    async with dbsession as session:
        await session.execute(query)
        await session.commit()


@pytest.mark.asyncio
async def test_save_events(dbsession: AsyncSession, events_to_create: list[Event]):
    assert isinstance(events_to_create, list)
    assert len(events_to_create) == 2
    assert all(isinstance(e, Event) for e in events_to_create)

    repo = AsyncSQLAlchemyEventRepository(dbsession)

    result = await repo.saveMany(events_to_create)

    assert isinstance(result, Ok)
    created = result.unwrap()
    assert isinstance(created, list)
    assert len(created) == 2
    assert all(isinstance(e, Event) for e in created)

    # Commit to ensure persistence
    await dbsession.commit()
