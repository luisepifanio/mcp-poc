from typing import Protocol, TypeVar, runtime_checkable

from .repositories import CourseRepository
from .repository_event import EventRepository


@runtime_checkable
class UnitOfWork(Protocol):
    @property
    def courses(self) -> CourseRepository: ...

    @property
    def events(self) -> EventRepository: ...

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: str | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
