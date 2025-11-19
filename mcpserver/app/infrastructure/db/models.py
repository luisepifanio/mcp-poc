import enum
from datetime import UTC, datetime

# from sqlmodel import UUID          # 🔴
# from pydantic import UUID4 as UUID # 🟡
from uuid import (
    UUID,  # 🟡
    uuid4,
)
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from sqlalchemy.types import JSON
from sqlmodel import (  # , UUID
    TIMESTAMP,
    Column,
    Field,
    Relationship,
    SQLModel,
    text,
)

# from sqlmodel._compat import SQLModelConfig


def datetime_to_gmt_str(dt: datetime) -> str:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.isoformat()
    # return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def enum_values(enum_class: type[enum.Enum]) -> list:
    """Get values for enum."""
    return [status.value for status in enum_class]


class Base(SQLModel, table=False):
    model_config = {
        "json_encoders": {datetime: datetime_to_gmt_str},
        "populate_by_name": True,
    }  # type: ignore

    def serializable_dict(self, **kwargs):
        """Return a dict which contains only serializable fields."""
        default_dict = self.model_dump()

        return jsonable_encoder(default_dict)


class IntIdBase(Base, table=False):
    id: int | None = Field(default=None, primary_key=True)


class UUIDBase(Base, table=False):
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)


class CreatedUpdatedBase(SQLModel, table=False):
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
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
