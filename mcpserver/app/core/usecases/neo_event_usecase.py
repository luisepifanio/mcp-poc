from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TypedDict, cast

from result import Err, Ok, Result
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.errors import ErrorCatalog, ErrorDetail

from ..entities import Event, EventResultStructure, EventState, JSONDict
from ..processor_registry import (
    ProcessorRegistry,
)
from ..processor_registry import (
    processor_registry as global_processor_registry,
)
from ..processors import ErrorType, IEventProcessor, ProcessorResultStatus
from ..unit_of_work import UnitOfWork
from ..usecase import AsyncUseCase
from .event_usecases import EnqueuedEventUseCaseOutput as ProcessEventResult
from .event_usecases import transition_event
from .utils import async_chain

logger = logging.getLogger(__name__)


class ProcessEventIdealUseCase(
    AsyncUseCase[ProcessEventResult, Result[ProcessEventResult, ErrorDetail]]
):
    """
    Process an event with built-in retry logic (CORE business logic).

    Responsibility:
    - Validate event state
    - Lock event state (prevent concurrent processing)
    - Invoke processor with exponential backoff retries (3 attempts max)
    - Handle results: SUCCESS, PENDING_CALLBACK, FAILED
    - Persist final state

    **IMPORTANT**: Retry logic is CORE business logic, not infrastructure.
    Exponential backoff with max 3 attempts prevents cascade failures.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        processor_registry: ProcessorRegistry | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.uow = uow
        self.processor_registry = processor_registry or global_processor_registry
        self.max_attempts = max_attempts

    async def execute(
        self, event: ProcessEventResult
    ) -> Result[ProcessEventResult, ErrorDetail]:
        """
        Process event with automatic retries on transient errors.

        Orchestration using Result pattern matching (async-safe):
        1. Fetch fresh Event by ID from database
        2. Validate & lock state (PENDING→PROCESSING or TEMPORAL_ERROR→RETRYING)
        3. Process with retries (invoke processor, handle outcomes)
        4. Persist final outcome (SUCCESS→COMPLETED, EXHAUSTED→handle, etc.)

        All stages return Result[Event, ErrorDetail]. Each stage is awaited
        and matched; any Err short-circuits and returns immediately.

        Args:
            event: ProcessEventResult DTO with id, name, state, etc.

        Returns:
            Result[ProcessEventResult, ErrorDetail]: Final persisted event or error
        """
        # Stage 0: Fetch fresh Event from DB and compose stages
        fetch_result = await self.uow.events.getOne(event.id)
        result = await async_chain(fetch_result, self.validate_and_lock)
        result = await async_chain(result, self.process_with_retries)
        result = await async_chain(result, self.persist_outcome)

        # Map persisted Event -> ProcessEventResult DTO
        return result.map(lambda evt: self._as_output(evt))

    async def validate_and_lock(self, event: Event) -> Result[Event, ErrorDetail]:
        """Stage 1: Validate processable state, initialize typed context and persist lock.

        Accepts states: PENDING, TEMPORAL_ERROR, RETRYING.
        Transitions:
        - PENDING -> PROCESSING
        - TEMPORAL_ERROR -> RETRYING
        Persists lock via UnitOfWork.
        """
        allowed_states = {
            EventState.PENDING,
            EventState.TEMPORAL_ERROR,
            EventState.RETRYING,
        }
        if event.state not in allowed_states:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail=(
                        f"Invalid state {event.state}. Expected PENDING/TEMPORAL_ERROR/RETRYING"
                    ),
                )
            )

        processing_ctx = self._ensure_processing_context(event)

        state_mapping: dict[EventState, EventState] = {
            EventState.PENDING: EventState.PROCESSING,
            EventState.TEMPORAL_ERROR: EventState.RETRYING,
        }

        logger.debug(f"Before event {event.id} has state {event.state}")

        lock_res: Result[Event, ErrorDetail] = (
            transition_event(event, state_mapping[event.state])
            if event.state in state_mapping
            else Ok(event)
        )

        return await self._persist_lock(lock_res, processing_ctx)

    def _ensure_processing_context(self, event: Event) -> ProcessingContext:
        """Ensure event.context and processing context are initialized with defaults."""
        if event.context is None or not isinstance(event.context, dict):
            event.context = {}
        context: JSONDict = cast(JSONDict, event.context)

        proc_raw = context.get("processing") or {}
        processing_ctx_json: JSONDict = cast(
            JSONDict, proc_raw if isinstance(proc_raw, dict) else {}
        )
        context["processing"] = processing_ctx_json
        processing_ctx: ProcessingContext = cast(ProcessingContext, processing_ctx_json)

        now_iso = datetime.now(UTC).isoformat()
        processing_ctx.setdefault("started_at", now_iso)
        processing_ctx.setdefault(
            "last_activity", processing_ctx.get("started_at", now_iso)
        )
        processing_ctx.setdefault("attempts", [])
        processing_ctx.setdefault("pending_callback", False)
        processing_ctx.setdefault("retry_exhausted", False)

        return processing_ctx

    async def process_with_retries(self, event: Event) -> Result[Event, ErrorDetail]:
        """Stage 2: invoke processor with retries, updating in-memory context only."""
        context: JSONDict = cast(JSONDict, event.context or {})
        processing_ctx = self._ensure_processing_context(event)

        processor = self.processor_registry.get(event.name)
        processing_ctx["processor"] = processor.__class__.__name__

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0),
                retry=retry_if_exception(
                    lambda exc: processor.classify_error(exc) == ErrorType.TRANSIENT
                ),
                reraise=False,
            ):
                with attempt:
                    try:
                        proc_result = await processor.process(event)
                        processing_ctx["last_activity"] = datetime.now(UTC).isoformat()

                        match proc_result.status:
                            case ProcessorResultStatus.SUCCESS:
                                event.result = self._build_result(proc_result.data)
                                return Ok(event)
                            case ProcessorResultStatus.PENDING_CALLBACK:
                                processing_ctx["pending_callback"] = True
                                processing_ctx["callback_subject"] = (
                                    proc_result.callback_subject
                                )
                                processing_ctx["last_activity"] = datetime.now(
                                    UTC
                                ).isoformat()
                                if proc_result.metadata:
                                    processing_ctx["metadata"] = cast(
                                        JSONDict, proc_result.metadata
                                    )
                                return Ok(event)
                            case ProcessorResultStatus.FAILED:
                                self._record_error(
                                    context,
                                    proc_result.error or "Processor failed",
                                    processor,
                                )
                                if event.state in {
                                    EventState.PROCESSING,
                                    EventState.RETRYING,
                                }:
                                    transition_event(event, EventState.TEMPORAL_ERROR)
                                return Err(
                                    ErrorDetail(
                                        error=ErrorCatalog.RUNTIME_FAILED.value,
                                        detail=proc_result.error or "Processor failed",
                                    )
                                )
                    except BaseException as exc:  # noqa: BLE001
                        processing_ctx.setdefault("attempts", []).append(
                            {
                                "attempt_number": attempt.retry_state.attempt_number,
                                "timestamp": datetime.now(UTC).isoformat(),
                                "error": str(exc),
                            }
                        )
                        processing_ctx["last_activity"] = datetime.now(UTC).isoformat()
                        if event.state in {EventState.PROCESSING, EventState.RETRYING}:
                            transition_event(event, EventState.TEMPORAL_ERROR)
                        raise
        except RetryError as exc:
            last_exc = exc.last_attempt.exception()
            error_type = processor.classify_error(
                last_exc if last_exc is not None else Exception("Unknown")
            )
            processing_ctx["retry_exhausted"] = True
            processing_ctx["last_activity"] = datetime.now(UTC).isoformat()
            self._record_error(
                context, str(last_exc) if last_exc else "Unknown", processor
            )
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.RUNTIME_FAILED.value,
                    detail=(
                        f"Failed after {self.max_attempts} attempts: {str(last_exc) if last_exc else 'Unknown'}"
                    ),
                    metadata={"error_type": error_type.value},
                )
            )

        return Err(
            ErrorDetail(
                error=ErrorCatalog.RUNTIME_FAILED.value,
                detail="Unexpected processing flow end",
            )
        )

    async def persist_outcome(self, event: Event) -> Result[Event, ErrorDetail]:
        """Stage 3: Persist final outcome and commit (TX2).

        Rules:
        - SUCCESS → COMPLETED (from PROCESSING or RETRYING)
        - PENDING_CALLBACK → persist context only, no state change
        - RETRY EXHAUSTED → if last transition was RETRYING→TEMPORAL_ERROR, transition to EXHAUSTED
        - Otherwise (TEMPORAL_ERROR without exhaustion) → persist context only
        """
        processing_ctx = self._ensure_processing_context(event)

        # SUCCESS: event.result present → COMPLETED
        if event.result is not None:
            if event.state in {EventState.PROCESSING, EventState.RETRYING}:
                tr = transition_event(event, EventState.COMPLETED)
                if tr.is_err():
                    return Err(tr.unwrap_err())
            processing_ctx["last_activity"] = datetime.now(UTC).isoformat()
            saved = await self.uow.events.save(event)
            match saved:
                case Err(ed):
                    return Err(ed)
                case Ok(persisted):
                    await self.uow.commit()
                    return Ok(persisted)

        # PENDING_CALLBACK: persist context (no state change)
        if bool(processing_ctx.get("pending_callback", False)):
            processing_ctx["last_activity"] = datetime.now(UTC).isoformat()
            saved = await self.uow.events.save(event)
            match saved:
                case Err(ed):
                    return Err(ed)
                case Ok(persisted):
                    await self.uow.commit()
                    return Ok(persisted)

        # RETRY EXHAUSTED: Transition RETRYING→EXHAUSTED if applicable
        exhausted = bool(processing_ctx.get("retry_exhausted", False))
        if exhausted:
            last_from_state = self._last_from_state_to_temporal_error(event)
            if last_from_state == EventState.RETRYING:
                tr1 = transition_event(event, EventState.RETRYING)
                if tr1.is_err():
                    return Err(tr1.unwrap_err())
                tr2 = transition_event(event, EventState.EXHAUSTED)
                if tr2.is_err():
                    return Err(tr2.unwrap_err())
            # Record failure metadata
            processing_ctx["failed_at"] = datetime.now(UTC).isoformat()
            attempts = processing_ctx.get("attempts") or []
            processing_ctx["retry_count"] = (
                len(attempts) if isinstance(attempts, list) else 0
            )
            processing_ctx["last_activity"] = datetime.now(UTC).isoformat()
            saved = await self.uow.events.save(event)
            match saved:
                case Err(ed):
                    return Err(ed)
                case Ok(persisted):
                    await self.uow.commit()
                    return Ok(persisted)

        # Default: TEMPORAL_ERROR without exhaustion → persist context only
        processing_ctx["last_activity"] = datetime.now(UTC).isoformat()
        saved = await self.uow.events.save(event)
        match saved:
            case Err(ed):
                return Err(ed)
            case Ok(persisted):
                await self.uow.commit()
                return Ok(persisted)

    def _last_from_state_to_temporal_error(self, event: Event) -> EventState | None:
        """Return the from_state of the last transition that ended in TEMPORAL_ERROR."""
        transitions = event.transitions or []
        for tr in reversed(transitions):
            try:
                if tr.to_state == EventState.TEMPORAL_ERROR:
                    return tr.from_state
            except Exception:
                continue
        return None

    def _build_result(self, data: dict[str, object] | None) -> EventResultStructure:
        payload: JSONDict = cast(JSONDict, data or {})
        return {"payload": payload}

    def _as_output(self, event: Event) -> ProcessEventResult:
        """Convert Event entity to ProcessEventResult (EnqueuedEventUseCaseOutput) DTO."""
        return ProcessEventResult(
            id=event.id,
            name=event.name,
            state=event.state,
            external_uuid=event.external_uuid,
            payload=event.payload,
            context=event.context,
            result=event.result,
        )

    def _record_error(
        self, context: JSONDict, message: str, processor: IEventProcessor
    ) -> None:
        err_ctx = cast(JSONDict, context.get("error") or {})
        err_ctx["message"] = message
        err_ctx["processor"] = processor.__class__.__name__
        err_ctx["occurred_at"] = datetime.now(UTC).isoformat()
        context["error"] = err_ctx

    async def _persist_lock(
        self, lock_res: Result[Event, ErrorDetail], processing_ctx: ProcessingContext
    ) -> Result[Event, ErrorDetail]:
        match lock_res:
            case Err(ed):
                logger.error(f"Error locking event: {ed}")
                return Err(ed)
            case Ok(ev):
                logger.debug(f"After event {ev.id} has state {ev.state}")
                saved = await self.uow.events.save(ev)
                match saved:
                    case Err(ed):
                        logger.error(f"Error saving locked event: {ed}")
                        return Err(ed)
                    case Ok(persisted):
                        processing_ctx["last_activity"] = datetime.now(UTC).isoformat()
                        await self.uow.commit()
                        return Ok(persisted)


class ProcessingAttempt(TypedDict, total=False):
    attempt_number: int
    timestamp: str
    error: str | None


class ProcessingContext(TypedDict, total=False):
    started_at: str
    last_activity: str
    processor: str | None
    attempts: list[ProcessingAttempt]
    pending_callback: bool
    callback_subject: str | None
    metadata: JSONDict | None
    retry_exhausted: bool
    failed_at: str | None
    retry_count: int


# (method moved into class)
