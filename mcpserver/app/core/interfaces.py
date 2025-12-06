from typing import Protocol, runtime_checkable
from uuid import UUID

from result import Result

from app.errors import ErrorDetail

from .entities import Course, Event


@runtime_checkable
class CourseRepositoryProtocol(Protocol):
    async def get_courses(self, course_ids: list[str]) -> list[Course]: ...

    async def get_course(self, course_id: str) -> Course: ...

    async def save_course(self, course: Course) -> None: ...


@runtime_checkable
class EventRepositoryProtocol(Protocol):
    async def delete(
        self, event: Event, hard: bool = False
    ) -> Result[bool, ErrorDetail]: ...

    async def get_by_external_uuid(
        self, external_uuid: UUID
    ) -> Result[Event, ErrorDetail]: ...

    async def getMany(self, ids: list[UUID]) -> Result[list[Event], ErrorDetail]: ...

    async def saveMany(self, events: list[Event]) -> Result[list[Event], ErrorDetail]: ...


@runtime_checkable
class UnitOfWorkProtocol(Protocol):
    courses: CourseRepositoryProtocol
    events: EventRepositoryProtocol

    async def __aenter__(self) -> "UnitOfWorkProtocol": ...

    async def __aexit__(self, exc_type, exc_val, exc_tb): ...

    async def commit(self): ...

    async def rollback(self): ...
