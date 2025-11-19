from pydantic import Field
from pydantic.dataclasses import dataclass

from app.infrastructure.db.models import Course

from ..unit_of_work import UnitOfWork
from ..usecase import AsyncUseCase


@dataclass
class GetCourseUseCaseInput:
    courses: list[str] = Field(default_factory=list)
    force_scrap: bool = Field(default=False)


class GetAsyncCourseUseCase(AsyncUseCase[GetCourseUseCaseInput, list[Course]]):
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, input_port: GetCourseUseCaseInput) -> list[Course]:
        async with self.uow:
            if input_port.force_scrap:
                pass  # TODO: implement force scrap logic
            return await self.uow.course.get_courses(input_port.courses)


class CreateCourseUseCase:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, course: Course) -> None:
        async with self.uow:
            await self.uow.course.save_course(course)
