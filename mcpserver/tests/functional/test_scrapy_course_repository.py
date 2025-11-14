import json

import pytest

from app.infrastructure.db.models import Course
from app.infrastructure.scrapy_spider.repository import ScrapyCourseRepository


@pytest.mark.asyncio
async def test_scap_courses():
    cookies: dict = {}
    with open("var/lib/cookies.json") as f:
        cookies.update(json.load(f))

    unit: ScrapyCourseRepository = ScrapyCourseRepository(cookies=cookies)

    courses: list[Course] = await unit.get_courses(["67902", "97596"])
    assert isinstance(courses, list)
    assert all(isinstance(course, Course) for course in courses)
    assert len(courses) == 2
