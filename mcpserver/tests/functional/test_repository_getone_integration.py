from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import Event
from app.errors import ErrorCatalog


@pytest.mark.asyncio
async def test_asyncsqlalchemyeventrepo_getone_ok_and_not_found(uow_factory) -> None:
    """Integration test: persist an Event via the real repository and verify getOne behavior."""
    # Use the provided uow_factory to obtain a UnitOfWork instance
    async with uow_factory() as uow:
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
