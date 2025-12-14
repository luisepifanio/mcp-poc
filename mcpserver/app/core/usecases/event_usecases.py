import json
from uuid import UUID, uuid4

from pydantic import Field, RootModel, ValidationError
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
    payload: JSONDict = Field()
    id: UUID | None = Field(default_factory=uuid4)
    external_uuid: UUID | None = Field(default_factory=uuid4)
    context: JSONDict | None = Field(default_factory=dict)
    state: EventState | None = EventState.CREATED


# input_adapter = TypeAdapter(EventUseCaseInput)


@pydantic_dataclass(frozen=True)
class EventUseCaseOutput:
    name: str = Field(max_length=100)
    payload: JSONDict = Field()
    id: UUID = Field()
    state: EventState = Field()
    external_uuid: UUID | None = Field()
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
        """
        Enqueues an event for processing.
        1. Assumes idempotency by external_uuid first, then by id second
        2. Validation executed before saving an event
            2.1 Allowed states to enqueue: CREATED or None (default to CREATED)
            2.2 JSONDict fields are re-encoded with `json.dumps(data, sort_keys=True)` to ensure consistent storage and comparison and even hashing if needed
            2.3 All pydantic validations are executed on inputs and before returning use case output
        3. If an integrity error occurs (e.g., duplicate external_uuid or id ), it returns existing event with that identifier instead of creating a new one.
        4. If event with the same external_uuid or id exists, it is returned as is, without any state changes.
        5. The only responsability of this use case is to enqueue an event in PENDING state if it is new, there will be no processing logic here.
        6. All related about processing event is on his own case `InLineProcessEventUseCase` and `AsyncProcessEventUseCase`

        Args:
            input (EventUseCaseInput): Input data for the event to be enqueued.

        Returns:
            Result[EventUseCaseOutput, ErrorDetail]: Result containing the enqueued event output or an error detail.
            If event has been just created it is expected to be in PENDING state, otherwise it is returned as is in current state.
        """
        # TODO: Migrate to functional approach result.map_or_else
        # 1) Validate input pydantic dataclass (constructor should have run validations already)
        try:
            # Re-constructing a RootModel ensures pydantic validation of the dataclass fields
            RootModel[EventUseCaseInput](input)
        except ValidationError as exc:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail=str(exc),
                )
            )

        async with self.uow:
            existing_event = None
            # Check by external_uuid first
            if input.external_uuid is not None:
                # Check if event with the same external_uuid already exists
                existing_event = await self.uow.events.get_by_external_uuid(
                    input.external_uuid
                )
            match existing_event:
                case Ok(event):
                    # Event with the same external_uuid already exists
                    return Ok(self.as_output(event))

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
                    # Validate allowed enqueue state: only CREATED or None
                    if input.state is not None and input.state is not EventState.CREATED:
                        return Err(
                            ErrorDetail(
                                error=ErrorCatalog.VALIDATION_FAILED.value,
                                detail=(
                                    f"Invalid initial state for enqueue: {input.state}. "
                                    "Only CREATED or None are allowed."
                                ),
                            )
                        )

                    # Normalize JSON fields to deterministic representation
                    normalized_payload = self._normalize_json(input.payload)
                    normalized_context = self._normalize_json(input.context)

                    evt = Event(
                        name=input.name,
                        external_uuid=input.external_uuid,
                        payload=normalized_payload or {},
                        context=normalized_context or {},
                        state=input.state or EventState.CREATED,
                    )

                    # apply transition to PENDING before saving (this use case only enqueues)
                    event_result = transition_event(evt, EventState.PENDING)

                    match event_result:
                        case Ok(event):
                            # Use save_or_resolve for idempotent behavior:
                            # - Uses SAVEPOINTs to isolate each insert
                            # - On conflict, resolves to existing row without breaking transaction
                            save_result = await self.uow.events.save_or_resolve([evt])
                            match save_result:
                                case Ok(saved_events):
                                    # save_or_resolve returns a list
                                    if len(saved_events) != 1:
                                        return Err(
                                            ErrorDetail(
                                                error=ErrorCatalog.RUNTIME_FAILED.value,
                                                detail=(
                                                    "Repository returned unexpected number of events"
                                                ),
                                            )
                                        )
                                    saved_model = saved_events[0]

                                    # Validate output via pydantic before returning
                                    try:
                                        out = self.as_output(saved_model)
                                        RootModel[EventUseCaseOutput](out)
                                    except ValidationError as exc:
                                        return Err(
                                            ErrorDetail(
                                                error=ErrorCatalog.VALIDATION_FAILED.value,
                                                detail=str(exc),
                                            )
                                        )
                                    return Ok(out)

                                case Err(err_detail):
                                    # If integrity/unique constraint, try to return existing canonical entity
                                    detail_text = (err_detail.detail or "").lower()
                                    if (
                                        "unique" in detail_text
                                        or "constraint" in detail_text
                                    ):
                                        # try to find by external_uuid then id
                                        if evt.external_uuid is not None:
                                            existing = await self.uow.events.get_by_external_uuid(
                                                evt.external_uuid
                                            )
                                            if isinstance(existing, Ok):
                                                return Ok(
                                                    self.as_output(existing.unwrap())
                                                )
                                        # fallback to id lookup
                                        existing = await self.uow.events.getOne(evt.id)
                                        if isinstance(existing, Ok):
                                            return Ok(self.as_output(existing.unwrap()))
                                    return Err(err_detail)

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

    @staticmethod
    def _normalize_json(value: JSONDict | None) -> JSONDict | None:
        """Return a deterministic JSON-compatible mapping for storage/comparison.

        The function serializes with `sort_keys=True` and deserializes back to
        a dict to ensure stable ordering of nested mappings. If serialization
        fails for any reason, the original value is returned unchanged.
        """
        if value is None:
            return None
        try:
            return json.loads(json.dumps(value, sort_keys=True))
        except Exception:
            return value

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
