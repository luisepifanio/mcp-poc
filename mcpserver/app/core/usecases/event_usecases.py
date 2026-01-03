import json
from datetime import UTC
from typing import cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, RootModel, ValidationError
from result import Err, Ok, Result

from app.errors import ErrorCatalog, ErrorDetail

from ..entities import Event, EventResultStructure, EventState, EventTransition, JSONDict
from ..unit_of_work import UnitOfWork
from ..usecase import AsyncUseCase

LOOKUP_EVENT_NAMES = {"GetEventById", "GetEventByExternalId"}


class EnqueuedEventUseCaseInput(BaseModel):
    name: str = Field(max_length=100)
    payload: JSONDict = Field()
    id: UUID | None = Field(default_factory=uuid4)
    external_uuid: UUID | None = Field(default_factory=uuid4)
    context: JSONDict | None = Field(default_factory=lambda: {})
    state: EventState | None = EventState.CREATED


class EnqueuedEventUseCaseOutput(BaseModel):
    name: str = Field(max_length=100)
    payload: JSONDict = Field()
    id: UUID = Field()
    state: EventState = Field()
    external_uuid: UUID | None = Field(default=None)
    context: JSONDict | None = Field(default_factory=lambda: {})
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
    AsyncUseCase[
        EnqueuedEventUseCaseInput, Result[EnqueuedEventUseCaseOutput, ErrorDetail]
    ]
):
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(
        self, input: EnqueuedEventUseCaseInput
    ) -> Result[EnqueuedEventUseCaseOutput, ErrorDetail]:
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
            RootModel[EnqueuedEventUseCaseInput](input)
        except ValidationError as exc:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail=str(exc),
                )
            )

        # 2) Extra validations and saving within UoW transaction
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

        # NOTE: Caller (infrastructure handler) manages transaction context.
        # This UseCase assumes an active transaction via UnitOfWork.
        # See: docs/TRANSACTION_PATTERN.md

        # Normalize JSON fields to deterministic representation
        normalized_payload = self._normalize_json(input.payload)
        normalized_context = self._normalize_json(input.context)

        # Auto-generate UUID if not provided (analogous to database autoincrement)
        # This respects the Pydantic default_factory=uuid4 in EnqueuedEventUseCaseInput
        event_id = input.id if input.id is not None else uuid4()

        evt = Event(
            id=event_id,
            name=input.name,
            external_uuid=input.external_uuid,
            payload=normalized_payload or {},
            context=normalized_context or {},
            state=input.state or EventState.CREATED,
        )

        op_result = await self.uow.events.save_or_resolve_one(evt)

        # TODO: Implement transition to PENDING state just after publishing successfully
        # to redis stream, so for now we keep it as CREATED

        return op_result.and_then(lambda saved_event: Ok(self.as_output(saved_event)))

    def as_event_entity(self, input: EnqueuedEventUseCaseInput) -> Event:
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
            normalized = json.loads(json.dumps(value, sort_keys=True))
            return cast(JSONDict, normalized)
        except Exception:
            return value

    def as_output(self, event: Event) -> EnqueuedEventUseCaseOutput:
        return EnqueuedEventUseCaseOutput(
            id=event.id,
            name=event.name,
            state=event.state,
            external_uuid=event.external_uuid,
            payload=event.payload,
            context=event.context,
            result=event.result,
        )


class ProcessEventUseCase(
    AsyncUseCase[
        EnqueuedEventUseCaseInput, Result[EnqueuedEventUseCaseOutput, ErrorDetail]
    ]
):
    """
    Process an event using the processor pattern.

    Flow:
    1. Get processor from registry (defaults to NoOpProcessor if not registered)
    2. Execute processor.process(event)
    3. Handle result:
       - SUCCESS: Transition PROCESSING → COMPLETED
       - PENDING_CALLBACK: Transition PENDING → PROCESSING (waiting for callback)
       - FAILED: Classify error and decide on FAILED vs retry
    4. Update event context with processing metadata
    5. Save event with transitions
    """

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(
        self,
        input: Event | EnqueuedEventUseCaseInput,
        result_data: JSONDict | None = None,
        error: str | None = None,
        processing_metadata: JSONDict | None = None,
        is_failed: bool = False,
        is_temporal_error: bool = False,
    ) -> Result[EnqueuedEventUseCaseOutput, ErrorDetail]:
        """
        Execute event processing via processor pattern.

        Args:
            input: Event entity or EnqueuedEventUseCaseInput DTO to process
            result_data: Optional result data from processor (if SUCCESS)
            error: Optional error message (if FAILED or ERROR)
            processing_metadata: Optional metadata to store in context.processing
            is_failed: If True, mark as FAILED (PERMANENT error)
            is_temporal_error: If True, mark as TEMPORAL_ERROR (TRANSIENT error)

        Returns:
            Result with processed event or error detail
        """
        from datetime import datetime

        from app.core.processor_registry import processor_registry

        # Convert Event entity to EnqueuedEventUseCaseInput if needed
        if isinstance(input, Event):
            event_input = EnqueuedEventUseCaseInput(
                name=input.name,
                payload=input.payload or {},
                id=input.id,
                external_uuid=input.external_uuid,
                context=input.context or {},
                state=input.state,
            )
        else:
            event_input = input

        # Get processor (may be NoOpProcessor if not registered)
        processor = processor_registry.get(event_input.name)

        # Determine final state
        if is_failed:
            final_state = EventState.FAILED
        elif is_temporal_error:
            final_state = EventState.TEMPORAL_ERROR
        elif result_data is not None:
            final_state = EventState.COMPLETED
        else:
            final_state = EventState.PROCESSING

        # Transition event to final state
        transition_result = transition_event(event_input, final_state)
        if transition_result.is_err():
            return Err(transition_result.unwrap_err())

        # Update context with processing metadata
        if "processing" not in event_input.context:
            event_input.context["processing"] = {}

        event_input.context["processing"]["started_at"] = datetime.now(UTC).isoformat()
        event_input.context["processing"]["processor"] = processor.__class__.__name__

        # Add processor-specific metadata if provided
        if processing_metadata:
            event_input.context["processing"].update(processing_metadata)

        # Store result or error
        if result_data:
            event_input.result = result_data
            event_input.context["processing"]["completed_at"] = datetime.now(
                UTC
            ).isoformat()
        elif error:
            if "error" not in event_input.context:
                event_input.context["error"] = {}
            event_input.context["error"]["message"] = error
            event_input.context["error"]["processor"] = processor.__class__.__name__
            event_input.context["error"]["occurred_at"] = datetime.now(UTC).isoformat()

        # Save event with all transitions and context updates
        save_result = await self.uow.events.save(event_input)
        return save_result.and_then(lambda saved_event: Ok(self.as_output(saved_event)))

    def as_output(self, event: Event) -> EnqueuedEventUseCaseOutput:
        """Convert event entity to output DTO."""
        return EnqueuedEventUseCaseOutput(
            id=event.id,
            name=event.name,
            state=event.state,
            external_uuid=event.external_uuid,
            payload=event.payload,
            context=event.context,
            result=event.result,
        )
