from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.unit_of_work import AsyncSQLAlchwemyUnitOfWork


@pytest.mark.asyncio
async def test_unit_of_work_commit_and_close(mocker):
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    # Patch repository class to avoid constructing real repo
    mock_repo = MagicMock()
    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyCourseRepository",
        return_value=mock_repo,
    )

    async with AsyncSQLAlchwemyUnitOfWork(session) as uow:
        assert uow.session is session
        assert hasattr(uow, "courses")

    # After successful exit, commit and close must be awaited
    session.commit.assert_awaited()
    session.close.assert_awaited()


@pytest.mark.asyncio
async def test_unit_of_work_rollback_on_exception(mocker):
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyCourseRepository",
        return_value=MagicMock(),
    )

    with pytest.raises(ValueError):
        async with AsyncSQLAlchwemyUnitOfWork(session):
            raise ValueError("boom")

    session.rollback.assert_awaited()
    session.close.assert_awaited()
