from uuid import UUID

# Code below omitted 👇
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.core.entities import Course
from app.core.repositories import CourseRepository


class AsyncSQLAlchemyCourseRepository(CourseRepository):
    def __init__(self, session: AsyncSession):
        self.session: AsyncSession = session

    async def get_courses(self, course_ids: list[str]) -> list[Course]:
        # uuids: list[UUID] = [UUID(uid) for uid in course_ids]

        query = select(Course).where(col(Course.lms_id).in_(course_ids))
        result = await self.session.execute(query)
        # devuelve instancias ORM (list[Course])
        return list(result.scalars().all())

    async def get_course(self, course_id: str) -> Course:
        query = select(Course).where(col(Course.id) == UUID(course_id))
        result = await self.session.execute(query)
        course = result.scalar_one_or_none()
        if course is None:
            raise ValueError("Course not found")
        return course

    async def save_course(self, course: Course) -> None:
        # si Course es una entidad ORM, simplemente añadirla a la sesión
        self.session.add(course)
        await self.session.flush()
