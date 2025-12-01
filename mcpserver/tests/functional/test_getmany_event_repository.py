import logging

# Get a logger for this module
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from result import Err, Ok
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, delete

from app.core.entities import Event, EventState
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository

logger = logging.getLogger(__name__)


@pytest.fixture
async def events_in_db(dbsession: AsyncSession) -> AsyncGenerator[list[Event], None]:
    logger.debug("Setting up events to be created...")

    events: list[Event] = [
        Event(name="event_name_1", external_uuid=None, state=EventState.PENDING),
        Event(name="event_name_1", external_uuid=uuid4(), state=EventState.PROCESSING),
        Event(
            name="event_name_1",
            external_uuid=uuid4(),
            state=EventState.COMPLETED,
            deleted_at=datetime.now(),
        ),  # this event is soft-deleted
    ]

    # Insert events into the database, prior to yielding them
    async with dbsession as session:
        session.add_all(events)
        await session.commit()
        await session.flush()

    yield events
    logger.debug("Tearing down events after test function...")

    query = delete(Event).where(col(Event.id).in_([event.id for event in events]))
    async with dbsession as session:
        await session.execute(query)
        await session.commit()


@pytest.mark.asyncio
async def test_getmany_events(dbsession: AsyncSession, events_in_db: list[Event]):
    repo = AsyncSQLAlchemyEventRepository(dbsession)
    ids: list[UUID] = []
    ids += [
        event.id for event in events_in_db if event.id is not None
    ]  # get first two IDs

    result = await repo.getMany(ids)

    assert isinstance(result, Ok)
    fetched_events = result.unwrap()
    assert isinstance(fetched_events, list)
    assert len(fetched_events) == 2
    assert all(isinstance(e, Event) for e in fetched_events)

    # Commit to ensure persistence
    await dbsession.commit()


@pytest.mark.asyncio
async def test_getmany_runtime_error_handling(
    mocker, dbsession: AsyncSession, events_in_db: list[Event]
):
    mocker.patch("fastcrud.FastCRUD.get_multi", side_effect=ValueError("Mocked error"))

    repo = AsyncSQLAlchemyEventRepository(dbsession)
    ids: list[UUID] = []
    ids += [
        event.id for event in events_in_db if event.id is not None
    ]  # get first two IDs

    result = await repo.getMany(ids)

    assert isinstance(result, Err)
    error_detail = result.unwrap_err()
    assert error_detail.error == "RUNTIME_FAILED"
    assert "Mocked error" in error_detail.detail
