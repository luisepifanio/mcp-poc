from abc import ABC, abstractmethod

from .repositories import CourseRepository
from .respository_event import EventRepository


class UnitOfWork(ABC):
    courses: CourseRepository
    events: EventRepository

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass
