from dataclasses import dataclass

from app.infrastructure.db.models import Course

from .unit_of_work import UnitOfWork


@dataclass
class GetCourseUseCaseInput:
    courses: list[str]
    force_scrap: bool


class GetCourseUseCase:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, input: GetCourseUseCaseInput) -> list[Course]:
        async with self.uow:

            if input.force_scrap:
                pass  # TODO: implement force scrap logic
            return await self.uow.course.get_courses(input.courses)


class CreateCourseUseCase:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, course: Course) -> None:
        async with self.uow:
            await self.uow.course.save_course(course)
