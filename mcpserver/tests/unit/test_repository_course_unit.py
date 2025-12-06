from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Course
from app.infrastructure.db.repository import AsyncSQLAlchemyCourseRepository


@pytest.mark.asyncio
async def test_get_courses_and_get_course_and_save_course():
    session = MagicMock(spec=AsyncSession)
    # Mock execute return for get_courses
    fake_result = MagicMock()
    course1 = Course(title="t", description="d", lms_id="lms1")
    fake_result.scalars.return_value.all.return_value = [course1]
    session.execute = AsyncMock(return_value=fake_result)

    repo = AsyncSQLAlchemyCourseRepository(session)

    courses = await repo.get_courses(["lms1"])  # should return list with course1
    assert isinstance(courses, list)
    assert len(courses) == 1

    # get_course -> scalar_one_or_none
    fake_result2 = MagicMock()
    fake_result2.scalar_one_or_none.return_value = course1
    session.execute = AsyncMock(return_value=fake_result2)

    found = await repo.get_course(str(uuid4()))
    assert found is course1

    # save_course should call session.add and await flush
    session.add = MagicMock()
    session.flush = AsyncMock()

    await repo.save_course(course1)
    session.add.assert_called_once_with(course1)
    session.flush.assert_awaited()
