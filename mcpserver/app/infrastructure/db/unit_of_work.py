from sqlalchemy.ext.asyncio import AsyncSession

from ...core.unit_of_work import UnitOfWork
from .repository import AsyncSQLAlchemyCourseRepository
from .repository_event import AsyncSQLAlchemyEventRepository


class AsyncSQLAlchwemyUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession):
        self.session: AsyncSession | None = None
        self.__internal_session = session

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self.__internal_session
        self.courses = AsyncSQLAlchemyCourseRepository(self.session)
        self.events = AsyncSQLAlchemyEventRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        assert self.session is not None
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        await self.session.close()

    async def commit(self):
        assert self.session is not None
        await self.session.commit()

    async def rollback(self):
        assert self.session is not None
        await self.session.rollback()
