import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from result import Err, Ok
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, delete, select

from app.core.entities import Event, EventState
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository

logger = logging.getLogger(__name__)


@pytest.fixture
async def events_in_db(dbsession: AsyncSession) -> AsyncGenerator[list[Event], None]:
    events: list[Event] = [
        Event(name="event_1", external_uuid=uuid4(), state=EventState.PROCESSING),
        Event(name="event_2", external_uuid=uuid4(), state=EventState.COMPLETED),
        Event(
            name="event_soft_deleted",
            external_uuid=uuid4(),
            state=EventState.COMPLETED,
            deleted_at=datetime.now(),
        ),
    ]

    # Insert events into the database
    async with dbsession as session:
        session.add_all(events)
        await session.commit()
        await session.flush()

    yield events

    # Teardown
    query = delete(Event).where(col(Event.id).in_([event.id for event in events]))
    async with dbsession as session:
        await session.execute(query)
        await session.commit()


@pytest.mark.asyncio
async def test_get_by_external_uuid_success(
    dbsession: AsyncSession, events_in_db: list[Event]
):
    repo = AsyncSQLAlchemyEventRepository(dbsession)

    # Choose the first non-deleted event
    target = next(e for e in events_in_db if e.deleted_at is None)
    assert target.external_uuid is not None

    result = await repo.get_by_external_uuid(target.external_uuid)

    assert isinstance(result, Ok)
    fetched = result.unwrap()
    assert isinstance(fetched, Event)
    assert fetched.external_uuid == target.external_uuid
    assert fetched.id == target.id


@pytest.mark.asyncio
async def test_get_by_external_uuid_not_found(dbsession: AsyncSession):
    repo = AsyncSQLAlchemyEventRepository(dbsession)

    # Use a random uuid that was not inserted
    missing_uuid = uuid4()

    result = await repo.get_by_external_uuid(missing_uuid)

    assert isinstance(result, Err)
    error_detail = result.unwrap_err()
    assert error_detail.error == "NOT_FOUND"
    assert str(missing_uuid) in error_detail.detail


@pytest.mark.asyncio
async def test_get_by_external_uuid_soft_deleted_returns_not_found(
    dbsession: AsyncSession, events_in_db: list[Event]
):
    repo = AsyncSQLAlchemyEventRepository(dbsession)

    # Find the soft-deleted event
    soft_deleted = next(e for e in events_in_db if e.deleted_at is not None)
    assert soft_deleted.external_uuid is not None

    result = await repo.get_by_external_uuid(soft_deleted.external_uuid)

    assert isinstance(result, Err)
    error_detail = result.unwrap_err()
    assert error_detail.error == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_by_external_uuid_runtime_error_handling(
    mocker, dbsession: AsyncSession, events_in_db: list[Event]
):
    # Force FastCRUD.get to raise an error to simulate runtime failure
    mocker.patch("fastcrud.FastCRUD.get", side_effect=ValueError("Mocked error"))

    repo = AsyncSQLAlchemyEventRepository(dbsession)

    target = next(e for e in events_in_db if e.deleted_at is None)

    result = await repo.get_by_external_uuid(target.external_uuid)

    assert isinstance(result, Err)
    error_detail = result.unwrap_err()
    assert error_detail.error == "RUNTIME_FAILED"
    assert "Mocked error" in error_detail.detail
