from abc import ABC, abstractmethod

from .entities import Course


class RetrieveCourseRepository(ABC):
    @abstractmethod
    async def get_courses(self, course_ids: list[str]) -> list[Course]:
        pass


class CourseRepository(RetrieveCourseRepository):
    @abstractmethod
    async def get_course(self, course_id: str) -> Course:
        pass

    @abstractmethod
    async def save_course(self, course: Course) -> None:
        pass
