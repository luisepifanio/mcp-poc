from uuid import uuid4

import pytest
from result import Ok, Err

from app.core.entities import Event
from app.errors import ErrorCatalog


@pytest.mark.asyncio
async def test_asyncsqlalchemyeventrepo_getone_ok_and_not_found():
    """Integration test: persist an Event via the real repository and verify getOne behavior."""
    from app.infrastructure.db.connection import get_session_local

    AsyncSessionLocal = await get_session_local()

    # Use a fresh async session and the real UnitOfWork which instantiates the real repo
    async with AsyncSessionLocal() as session:
        from app.infrastructure.db.unit_of_work import AsyncSQLAlchwemyUnitOfWork

        async with AsyncSQLAlchwemyUnitOfWork(session) as uow:
            repo = uow.events

            # Create and save a new Event
            ev = Event(name="integration-getone", external_uuid=uuid4(), payload={"a": 1})
            saved_res = await repo.save(ev)
            assert isinstance(saved_res, Ok)
            saved = saved_res.unwrap()
            assert saved.id is not None

            # Fetch by id -> Ok
            fetched_res = await repo.getOne(saved.id)
            assert isinstance(fetched_res, Ok)
            fetched = fetched_res.unwrap()
            assert fetched.id == saved.id
            assert fetched.external_uuid == saved.external_uuid

            # Fetch by random id -> Not Found
            missing_res = await repo.getOne(uuid4())
            assert isinstance(missing_res, Err)
            assert missing_res.unwrap_err().error == ErrorCatalog.NOT_FOUND.value
