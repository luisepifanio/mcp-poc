from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import Enum as SQLEnum
from sqlmodel import Column, Enum, Field, Relationship

# Sacrilege: breaks some clean arch depending on infrastructure in core
from app.infrastructure.db.models import AuditableBase, UUIDBase


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
    califications: dict[str, float] = Field(sa_column=Column(JSON))
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
        sa_column=Column(SQLEnum(EventState)),
    )
    to_state: EventState = Field(
        sa_column=Column(SQLEnum(EventState)),
    )
    transition_date: datetime = Field(default=datetime.now)
    event_id: UUID = Field(foreign_key="events.id")
    event: "Event" = Relationship(back_populates="transitions")


class Event(UUIDBase, AuditableBase, table=True):
    __tablename__: str = "events"  #  type: ignore
    name: str = Field(max_length=100)
    external_uuid: UUID | None = Field(unique=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    context: dict | None = Field(default_factory=dict, sa_column=Column(JSON))
    state: EventState | None = Field(sa_column=Column(Enum(EventState)))
    transitions: list[EventTransition] = Relationship(back_populates="event")
    # Declare the JSON column
    result: dict | None = Field(default=None, sa_column=Column(JSON))
