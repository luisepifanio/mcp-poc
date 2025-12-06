from typing import Protocol

from .repositories import CourseRepository
from .respository_event import EventRepository


class UnitOfWork(Protocol):
    courses: CourseRepository
    events: EventRepository

    async def __aenter__(self) -> "UnitOfWork":
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        ...

    async def commit(self):
        ...

    async def rollback(self):
        ...
