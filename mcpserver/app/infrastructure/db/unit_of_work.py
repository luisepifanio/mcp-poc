import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories import CourseRepository
from app.core.repository_event import EventRepository

from ...core.unit_of_work import UnitOfWork
from .repository import AsyncSQLAlchemyCourseRepository
from .repository_event import AsyncSQLAlchemyEventRepository

logger = logging.getLogger(__name__)


class AsyncSQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession, owns_session: bool = False):
        """
        Initialize UnitOfWork with a session.

        Args:
            session: AsyncSession instance to manage.
            owns_session: If True, UoW is responsible for closing the session.
                         If False (default), session is managed externally (e.g., by FastAPI Depends).
        """
        self._session: AsyncSession = session
        self._owns_session: bool = owns_session
        self._courses: CourseRepository | None = None
        self._events: EventRepository | None = None

    @property
    def session(self) -> AsyncSession:
        assert self._session is not None, "Unit of Work has not been initialized."
        return self._session

    @property
    def courses(self) -> CourseRepository:
        assert self._courses is not None, "Unit of Work has not been initialized."
        return self._courses

    @property
    def events(self) -> EventRepository:
        assert self._events is not None, "Unit of Work has not been initialized."
        return self._events

    async def __aenter__(self) -> "AsyncSQLAlchemyUnitOfWork":
        self._courses = AsyncSQLAlchemyCourseRepository(self._session)
        self._events = AsyncSQLAlchemyEventRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: str | None,
    ) -> None:
        assert self.session is not None
        try:
            if exc_type is not None:
                await self.rollback()
            else:
                await self.commit()
        finally:
            # Only close session if we own it and it's still active
            if self._owns_session and self._is_session_active():
                try:
                    await self._session.close()
                except Exception as e:
                    logger.warning(f"Error closing session: {e}")
            self._courses = None
            self._events = None

    def _is_session_active(self) -> bool:
        """
        Check if the session is still active (not closed).

        Returns:
            bool: True if session is active, False if already closed.
        """
        try:
            # Check if session is still bound to a connection pool
            is_active = self._session.is_active
            return bool(is_active)
        except Exception:
            # If any error checking status, assume inactive
            return False

    async def commit(self) -> None:
        assert self.session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        assert self.session is not None
        await self._session.rollback()
