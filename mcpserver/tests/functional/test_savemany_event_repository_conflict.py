import logging
from uuid import uuid4

import pytest
from result import Ok
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.entities import Event, EventState
from app.infrastructure.db.repository_event import AsyncSQLAlchemyEventRepository

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_saveMany_does_not_update_on_conflict(dbsession: AsyncSession):
    """Ensure that saveMany does not silently update an existing row on uniqueness conflict.

    Steps:
    - Insert a canonical Event with a given external_uuid.
    - Attempt to saveMany() a different Event instance with the same external_uuid
      but different fields (name/state).
    - Assert the repository returned the canonical row and that the DB row's
      original fields were not modified.
    """
    ext = uuid4()

    # Create canonical event
    canonical = Event(name="original-name", external_uuid=ext, state=EventState.CREATED)
    dbsession.add(canonical)
    await dbsession.commit()

    # Build a conflicting event with same external_uuid but different values
    conflicting = Event(name="hacked-name", external_uuid=ext, state=EventState.COMPLETED)

    repo = AsyncSQLAlchemyEventRepository(dbsession)
    result = await repo.saveMany([conflicting])

    assert isinstance(result, Ok)
    created = result.unwrap()
    assert isinstance(created, list)
    assert len(created) == 1

    returned = created[0]
    assert returned.external_uuid == ext

    # Re-fetch from DB to ensure the canonical row was not updated
    q = select(Event).where(Event.external_uuid == ext)
    res = await dbsession.execute(q)
    fetched: Event = res.scalar_one()

    assert fetched.name == "original-name"
    assert fetched.state == EventState.CREATED

    # ensure returned row matches persisted canonical
    assert returned.id == fetched.id
    assert returned.name == fetched.name
    assert returned.state == fetched.state
