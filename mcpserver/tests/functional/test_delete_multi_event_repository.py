import logging

# Get a logger for this module
from collections.abc import AsyncGenerator
from datetime import datetime
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from result import Err, Ok
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, delete, select

from app.core.entities import Event, EventState
from app.infrastructure.db.repository_event import (
    AsyncSQLAlchemyEventRepository,
    DeleteTypedDict,
)

logger = logging.getLogger(__name__)


@pytest.fixture
async def events_in_db(dbsession: AsyncSession) -> AsyncGenerator[list[Event], None]:
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

    query = delete(Event).where(col(Event.id).in_([event.id for event in events]))
    async with dbsession as session:
        await session.execute(query)
        await session.commit()


@pytest.mark.asyncio
async def test_soft_delete(dbsession: AsyncSession, events_in_db: list[Event]):
    repo = AsyncSQLAlchemyEventRepository(dbsession)

    event_to_delete = events_in_db[0]

    result = await repo.delete(event_to_delete)

    assert isinstance(result, Ok)
    deleted_event = result.unwrap()
    assert isinstance(deleted_event, bool)
    assert deleted_event is True

    # Verify that the event is soft-deleted in the database
    async with dbsession as session:
        query = select(Event).where(Event.id == event_to_delete.id)
        db_event = (await session.execute(query)).scalar_one_or_none()
        assert db_event is not None
        assert db_event.deleted_at is not None


@pytest.mark.asyncio
async def test_hard_delete(dbsession: AsyncSession, events_in_db: list[Event]):
    repo = AsyncSQLAlchemyEventRepository(dbsession)

    event_to_delete = events_in_db[0]

    result = await repo.delete(event_to_delete, hard=True)

    assert isinstance(result, Ok)
    deleted_event = result.unwrap()
    assert isinstance(deleted_event, bool)
    assert deleted_event is True

    # Verify that the event is soft-deleted in the database
    async with dbsession as session:
        query = select(Event).where(Event.id == event_to_delete.id)
        db_event = (await session.execute(query)).scalar_one_or_none()
        assert db_event is None


@pytest.mark.asyncio
async def test_delete_runtime_error_handling(
    mocker, dbsession: AsyncSession, events_in_db: list[Event]
):
    repo = AsyncSQLAlchemyEventRepository(dbsession)
    event_to_delete = events_in_db[0]

    mocker.patch.object(repo, "getOne", side_effect=Exception("Mocked error"))

    result = await repo.delete(event_to_delete)

    assert isinstance(result, Err)
    error_detail = result.unwrap_err()
    assert error_detail.error == "RUNTIME_FAILED"
    assert "Mocked error" in error_detail.detail


@pytest.mark.asyncio
async def test_delete_many_events(dbsession: AsyncSession, events_in_db: list[Event]):
    events_in_db += [
        Event(
            id=uuid4(),
            name="event_not_in_db",
            external_uuid=None,
            state=EventState.COMPLETED,
        ),
    ]  # adding one more event intented not to be found
    repo = AsyncSQLAlchemyEventRepository(dbsession)

    result = await repo.delete_multi(events_in_db)

    assert isinstance(result, Ok)
    deleted_report: DeleteTypedDict = result.unwrap()
    assert isinstance(deleted_report, dict)
    assert (
        deleted_report["total_deleted"] == 2
    )  # only 2 events were soft-deleted, third one was already deleted
    assert deleted_report["deleted"] == [
        events_in_db[0].id,
        events_in_db[1].id,
    ]
    assert all(isinstance(e, UUID) for e in deleted_report["deleted"])
    # two events were not found (not in db)
    assert deleted_report["total_not_found"] == 2
    assert deleted_report["not_found"] == [
        events_in_db[2].id,
        events_in_db[3].id,
    ]

    # Commit to ensure persistence
    # await dbsession.commit()


@pytest.mark.asyncio
async def test_delete_many_events_error(dbsession: AsyncSession):
    events_in_db = [
        Event(
            id=None,
            name="event_not_in_db",
            external_uuid=None,
            state=EventState.COMPLETED,
        ),
    ]  # adding one more event intented not to be found
    repo = AsyncSQLAlchemyEventRepository(dbsession)

    result = await repo.delete_multi(events_in_db)

    assert isinstance(result, Err)
    error_detail = result.unwrap_err()
    assert error_detail.error == "VALIDATION_FAILED"
    assert error_detail.detail == "Event ID must be provided for deletion."
