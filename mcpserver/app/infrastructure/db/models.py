import enum
from datetime import datetime, timezone

# from sqlmodel import UUID          # 🔴
# from pydantic import UUID4 as UUID # 🟡
from uuid import (
    UUID,  # 🟡
    uuid4,
)

from sqlalchemy.types import JSON
from sqlmodel import TIMESTAMP, Column, Field, Relationship, SQLModel, text  # , UUID


def enum_values(enum_class: type[enum.Enum]) -> list:
    """Get values for enum."""
    return [status.value for status in enum_class]


class Base(SQLModel, table=False):
    pass


class IntIdBase(Base, table=False):
    id: int | None = Field(default=None, primary_key=True)


class UUIDBase(Base, table=False):
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)


class CreatedUpdatedBase(SQLModel, table=False):
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),  # This is key for auto-updating
        ),
    )


class UUIDAuditableBase(UUIDBase, CreatedUpdatedBase, table=False):
    pass


class UserOnCourseGrades(UUIDBase, table=True):
    califications: dict[str, float] = Field(sa_column=Column(JSON))
    name: str
    course_id: UUID | None = Field(default=None, foreign_key="course.id")


class Course(UUIDAuditableBase, table=True):
    title: str
    description: str
    lms_id: str = Field(index=True, nullable=False, unique=True)
    userGrades: list["UserOnCourseGrades"] = Relationship()
