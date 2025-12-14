from contextlib import asynccontextmanager

import pytest


@pytest.fixture
def uow_factory():
    """Provide a simple factory that returns an async contextmanager which
    yields an `AsyncSQLAlchwemyUnitOfWork` when given a session.

    This fixture is minimal and purpose-built for unit tests that already
    construct a fake `session` object (MagicMock).
    """
    from app.infrastructure.db.unit_of_work import AsyncSQLAlchwemyUnitOfWork

    @asynccontextmanager
    async def _factory(session=None):
        if session is None:
            raise RuntimeError("uow_factory requires a session for unit tests")
        async with AsyncSQLAlchwemyUnitOfWork(session) as uow:
            yield uow

    return _factory
