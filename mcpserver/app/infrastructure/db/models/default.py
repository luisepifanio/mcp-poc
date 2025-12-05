import enum
from datetime import UTC, datetime

# from sqlmodel import UUID          # 🔴
# from pydantic import UUID4 as UUID # 🟡
from uuid import (
    UUID,  # 🟡
    uuid4,
)
from zoneinfo import ZoneInfo

from sqlmodel import (  # , UUID
    TIMESTAMP,
    Column,
    Field,
    SQLModel,
    text,
)


def datetime_to_gmt_str(dt: datetime) -> str:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.isoformat()
    # return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def enum_values(enum_class: type[enum.Enum]) -> list:
    """Get values for enum."""
    return [status.value for status in enum_class]


class Base(SQLModel, table=False):
    pass


class IntIdBase(Base, table=False):
    id: int = Field(default=None, primary_key=True)


class UUIDBase(Base, table=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True)


class AuditableBase(Base, table=False):
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={
            # "sa_type": TIMESTAMP(timezone=True),
            "nullable": False,
            "server_default": text("CURRENT_TIMESTAMP"),
        },
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={
            # "sa_type": TIMESTAMP(timezone=True),
            "nullable": False,
            "server_default": text("CURRENT_TIMESTAMP"),
            "onupdate": text("CURRENT_TIMESTAMP"),
        },
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column_kwargs={
            # "sa_type": TIMESTAMP(timezone=True),
            "nullable": True,
        },
    )
