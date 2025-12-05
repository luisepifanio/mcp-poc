from uuid import UUID, uuid4

from pydantic import Field, RootModel
from pydantic.dataclasses import dataclass as pydantic_dataclass
from result import Err, Ok, Result

from app.errors import ErrorCatalog, ErrorDetail

from ..entities import Event, EventResultStructure, EventState, EventTransition, JSONDict
from ..unit_of_work import UnitOfWork
from ..usecase import AsyncUseCase

LOOKUP_EVENT_NAMES = {"GetEventById", "GetEventByExternalId"}


@pydantic_dataclass(frozen=True)
class EventUseCaseInput:
    name: str = Field(max_length=100)
    id: UUID | None = Field(default_factory=uuid4)
    external_uuid: UUID | None = Field(default_factory=uuid4)
    payload: JSONDict = Field(default_factory=dict)
    context: JSONDict | None = Field(default_factory=dict)
    state: EventState | None = EventState.CREATED


# input_adapter = TypeAdapter(EventUseCaseInput)


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


def transition_event(event: Event, new_state: EventState) -> Result[Event, ErrorDetail]:
    VALID_TRANSITIONS = {
        EventState.CREATED: [EventState.PENDING, EventState.FAILED],
        EventState.PENDING: [EventState.PROCESSING],  # IMPORTANT! Just one transition
        EventState.PROCESSING: [
            EventState.COMPLETED,
            EventState.FAILED,
            EventState.TEMPORAL_ERROR,
        ],
        EventState.COMPLETED: [],
        EventState.FAILED: [],
        EventState.TEMPORAL_ERROR: [
            EventState.RETRYING
        ],  # IMPORTANT! Just one transition
        EventState.RETRYING: [
            EventState.COMPLETED,
            EventState.EXHAUSTED,
            EventState.TEMPORAL_ERROR,
        ],
        EventState.EXHAUSTED: [],
    }
    valid_states: list[EventState] = VALID_TRANSITIONS.get(event.state, [])
    if new_state not in valid_states:
        return Err(
            ErrorDetail(
                error=ErrorCatalog.VALIDATION_FAILED.value,
                detail=f"( {event.state.value} , {new_state.value} )  is not a valid transition",
            )
        )

    # TODO: Validate event transitions
    if event.transitions is None:
        event.transitions = []

    event.transitions.append(
        EventTransition(
            event_id=event.id,
            from_state=event.state,
            to_state=new_state,
        )
    )
    event.state = new_state
    return Ok(event)


class EnqueueEventUseCase(
    AsyncUseCase[EventUseCaseInput, Result[EventUseCaseOutput, ErrorDetail]]
):
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(
        self, input: EventUseCaseInput
    ) -> Result[EventUseCaseOutput, ErrorDetail]:
        # TODO: Migrate to functional approach result.map_or_else
        async with self.uow:
            existing_event = None
            # Check by external_uuid first
            if input.external_uuid is not None:
                # Check if event with the same external_uuid already exists
                existing_event = await self.uow.events.getByExternalUUID(
                    input.external_uuid
                )
            match existing_event:
                case Ok(event):
                    # Event with the same external_uuid already exists
                    return self.as_output(event)

            # Check by id if not found by external_uuid
            existing_event = (
                await self.uow.events.getOne(input.id)
                if input.id
                else Err(
                    ErrorDetail(
                        error=ErrorCatalog.NOT_FOUND.value,
                        detail="No id or external_uuid provided for this event",
                    )
                )
            )
            match existing_event:
                case Ok(event):
                    # Event with the same id already exists
                    return Ok(self.as_output(event))
                case Err(error_detail) if (
                    input.name in LOOKUP_EVENT_NAMES
                    and error_detail.error == ErrorCatalog.NOT_FOUND.value
                ):
                    # piece of cake 🎂 , event lookup failed, just return error
                    return Err(error_detail)
                case Err(error_detail) if (
                    error_detail.error == ErrorCatalog.NOT_FOUND.value
                ):
                    evt = self.as_event_entity(input)
                    event_result = transition_event(evt, EventState.PENDING)

                    match event_result:
                        case Ok(event):
                            await self.uow.events.save(evt)
                            return Ok(self.as_output(event))
                        case Err(error):
                            return Err(error)
                case _:
                    return Err(
                        ErrorDetail(
                            error=ErrorCatalog.RUNTIME_FAILED.value,
                            detail="🐠 Please check this specific case",
                            metadata={
                                "input": RootModel[EventUseCaseInput](input).model_dump(
                                    mode="json"
                                )
                            },
                        )
                    )

    def as_event_entity(self, input: EventUseCaseInput) -> Event:
        return Event(
            # id=input.id or uuid4(),
            name=input.name,
            external_uuid=input.external_uuid,
            payload=dict(input.payload) if input.payload else {},
            context=dict(input.context) if input.context else {},
            state=input.state or EventState.CREATED,
        )

    def as_output(self, event: Event) -> EventUseCaseOutput:
        return EventUseCaseOutput(
            id=event.id,
            name=event.name,
            state=event.state,
            external_uuid=event.external_uuid,
            payload=event.payload,
            context=event.context,
            result=event.result,
        )
