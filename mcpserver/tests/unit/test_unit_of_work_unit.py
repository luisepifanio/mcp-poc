from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.unit_of_work import AsyncSQLAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_unit_of_work_commit_and_close(mocker) -> None:
    """Test that UoW commits and closes session when owns_session=True."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.is_active = True

    # Patch repository class to avoid constructing real repo
    mock_repo = MagicMock()
    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyEventRepository",
        return_value=mock_repo,
    )

    async with AsyncSQLAlchemyUnitOfWork(session, owns_session=True) as uow:
        assert uow.session is session
        assert hasattr(uow, "events")

    # After successful exit with owns_session=True, commit and close must be awaited
    session.commit.assert_awaited()
    session.close.assert_awaited()


@pytest.mark.asyncio
async def test_unit_of_work_not_close_when_not_owns_session(mocker) -> None:
    """Test that UoW does NOT close session when owns_session=False (default)."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    # Patch repository class
    mock_repo = MagicMock()
    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyEventRepository",
        return_value=mock_repo,
    )

    async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
        assert uow.session is session

    # After exit with owns_session=False, commit must be awaited but NOT close
    session.commit.assert_awaited()
    session.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_unit_of_work_rollback_on_exception(mocker):
    """Test that UoW rolls back and closes session on exception when owns_session=True."""
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.is_active = True

    mocker.patch(
        "app.infrastructure.db.unit_of_work.AsyncSQLAlchemyEventRepository",
        return_value=MagicMock(),
    )

    with pytest.raises(ValueError):
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=True):
            raise ValueError("boom")

    session.rollback.assert_awaited()
    session.close.assert_awaited()
