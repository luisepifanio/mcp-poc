from collections.abc import Mapping, Sequence
from enum import Enum as PyEnum
from typing import Any, NotRequired, TypedDict, Union
from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import Enum as SQLEnum
from sqlmodel import Column, Enum, Field, Relationship

# Sacrilege: breaks some clean arch depending on infrastructure in core
from app.infrastructure.db.models import AuditableBase, UUIDBase

type JSONScalar = str | int | float | bool | None

# alias nombrado y recursivo
type JSONValue = JSONScalar | JSONDict | JSONList

type JSONDict = Mapping[str, JSONValue]
type JSONList = Sequence[JSONValue]


class EventState(str, PyEnum):
    CREATED = "created"
    PENDING = "pending"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    EXHAUSTED = "exhausted"
    TEMPORAL_ERROR = "temporal_error"


class Evaluation(UUIDBase, table=True):
    califications: dict[str, Any] = Field(sa_column=Column(JSON))
    name: str
    course_id: UUID | None = Field(default=None, foreign_key="course.id")
    course: "Course" = Relationship(back_populates="evaluations")


class Course(UUIDBase, AuditableBase, table=True):
    title: str
    description: str
    lms_id: str = Field(index=True, nullable=False, unique=True)
    evaluations: list[Evaluation] = Relationship(back_populates="course")


class EventTransition(UUIDBase, table=True):
    __tablename__: str = "event_transitions"  #  type: ignore
    from_state: EventState | None = Field(
        default=None,
        # Usamos sa_column_kwargs para pasar el tipo SQLEnum
        sa_column_kwargs={
            "sa_type": SQLEnum(EventState),
            # SQLModel infiere 'nullable' de la pista de tipo (None |)
        },
    )
    to_state: EventState = Field(
        # Usamos sa_column_kwargs para pasar el tipo SQLEnum
        sa_column_kwargs={
            "sa_type": SQLEnum(EventState),
            # SQLModel infiere 'nullable=False' de la pista de tipo
        },
    )
    event_id: UUID = Field(
        foreign_key="events.id",
        ondelete="CASCADE",
    )
    event: "Event" = Relationship(back_populates="transitions")


class EventResultStructure(TypedDict):  # All keys are optional by default
    payload: JSONDict
    type: NotRequired[str]


# 🔴 IMPORTANT: using sa_column to define them could cause problems when using same column names in inherited classes
class Event(UUIDBase, AuditableBase, table=True):
    __tablename__: str = "events"  #  type: ignore
    name: str = Field(max_length=100)
    external_uuid: UUID | None = Field(unique=True, default=None)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    context: dict | None = Field(default_factory=dict, sa_column=Column(JSON))
    state: EventState = Field(
        sa_column=Column(Enum(EventState)), default=EventState.CREATED
    )
    transitions: list[EventTransition] = Relationship(
        back_populates="event", cascade_delete=True
    )
    # Declare the JSON column
    result: EventResultStructure | None = Field(
        default=None,
        sa_column=Column(JSON),
    )
