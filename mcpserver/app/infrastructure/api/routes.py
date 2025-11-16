import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.usecases import GetCourseUseCase, GetCourseUseCaseInput
from app.infrastructure.db.models import Course as CourseModel

from ..db.connection import get_session
from ..db.unit_of_work import AsyncSQLAlchwemyUnitOfWork

logger = logging.getLogger(__name__)

router = APIRouter()


class CourseQuery(BaseModel):
    courses: list[str] = Query(None, min_length=1)
    force_scrap: bool = Query(False)


@router.put("/courses")
async def save_courses(
    course: CourseModel,
    session: AsyncSession = Depends(get_session),
):
    pass


@router.get("/courses")
async def get_course(
    query: Annotated[CourseQuery, Query()],
    session: AsyncSession = Depends(get_session),
):
    logger.info(f"received: {query}")
    if False:
        return query
    else:
        uow = AsyncSQLAlchwemyUnitOfWork(session)
        usecase = GetCourseUseCase(uow)
        return await usecase.execute(
            GetCourseUseCaseInput(
                courses=query.courses,
                force_scrap=query.force_scrap,
            )
        )
