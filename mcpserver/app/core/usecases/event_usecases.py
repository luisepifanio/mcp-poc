from typing import NotRequired, TypedDict
from uuid import UUID, uuid4

from pydantic import Field
from pydantic.dataclasses import dataclass as pydantic_dataclass
from result import Err, Ok, Result

from app.errors import ErrorCatalog, ErrorDetail

from ..entities import Event, EventResultStructure, EventState, JSONDict
from ..unit_of_work import UnitOfWork
from ..usecase import AsyncUseCase


@pydantic_dataclass(frozen=True)
class EventUseCaseInput:
    name: str = Field(max_length=100)
    id: UUID | None = Field(default_factory=uuid4)
    external_uuid: UUID | None = Field(default_factory=uuid4)
    payload: JSONDict = Field(default_factory=dict)
    context: JSONDict | None = Field(default_factory=dict)
    state: EventState | None = EventState.CREATED


@pydantic_dataclass(frozen=True)
class EventUseCaseOutput:
    name: str = Field(max_length=100)
    id: UUID = Field()
    state: EventState = Field()
    external_uuid: UUID | None = Field()
    payload: JSONDict = Field(default_factory=dict)
    context: JSONDict | None = Field(default_factory=dict)
    # Declare the JSON column
    result: EventResultStructure | None = Field(default=None)


class EnqueueEventUseCase(
    AsyncUseCase[EventUseCaseInput, Result[EventUseCaseOutput, ErrorDetail]]
):
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(
        self, input: EventUseCaseInput
    ) -> Result[EventUseCaseOutput, ErrorDetail]:
        async with self.uow:
            existing_event = None
            if input.external_uuid is not None:
                # Check if event with the same external_uuid already exists
                existing_event = await self.uow.events.getByExternalUUID(
                    input.external_uuid
                )
            match existing_event:
                case Ok(event):
                    # Event with the same external_uuid already exists
                    return Ok(
                        EventUseCaseOutput(
                            id=event.id,
                            name=event.name,
                            state=event.state,
                            external_uuid=event.external_uuid,
                            payload=event.payload,
                            context=event.context,
                            result=event.result,
                        )
                    )
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.UNIMPLENTED.value,
                    detail="EnqueueEventUseCase is not implemented yet.",
                )
            )
