from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories import CourseRepository
from app.core.repository_event import EventRepository

from ...core.unit_of_work import UnitOfWork
from .repository import AsyncSQLAlchemyCourseRepository
from .repository_event import AsyncSQLAlchemyEventRepository


class AsyncSQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession):
        self._session = session
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
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        await self._session.close()
        self._courses = None
        self._events = None

    async def commit(self) -> None:
        assert self.session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        assert self.session is not None
        await self._session.rollback()
