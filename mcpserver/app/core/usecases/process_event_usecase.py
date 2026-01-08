from datetime import UTC, datetime
from typing import cast

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
from ..processor_registry import ProcessorRegistry
from ..processors import (
    ErrorType,
    IEventProcessor,
    ProcessorResult,
    ProcessorResultStatus,
)
from ..unit_of_work import UnitOfWork
from ..usecase import AsyncUseCase
from .event_usecases import EnqueuedEventUseCaseOutput as ProcessEventResult
from .event_usecases import transition_event


class ProcessEventUseCase2(AsyncUseCase[Event, Result[ProcessEventResult, ErrorDetail]]):
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
        processor_registry: ProcessorRegistry,
        max_attempts: int = 3,
    ) -> None:
        self.uow = uow
        self.processor_registry = processor_registry
        self.max_attempts = max_attempts

    async def execute(self, event: Event) -> Result[ProcessEventResult, ErrorDetail]:
        """
        Process event with automatic retries on transient errors.

        Flow:
        1. Validate state (PENDING, TEMPORAL_ERROR, RETRYING)
        2. Lock state: PENDING→PROCESSING or TEMPORAL_ERROR→RETRYING
        3. Persist lock to prevent concurrent processing
        4. Invoke processor with exponential backoff retries
        5. Handle result: SUCCESS/PENDING_CALLBACK/FAILED
        6. Persist final state

        Returns:
            Result[ProcessEventResult, ErrorDetail]
        """
        # Validate state
        if event.state not in {
            EventState.PENDING,
            EventState.TEMPORAL_ERROR,
            EventState.RETRYING,
        }:
            return Err(
                ErrorDetail(
                    error=ErrorCatalog.VALIDATION_FAILED.value,
                    detail=(
                        "Event must be PENDING, TEMPORAL_ERROR or RETRYING; "
                        f"found {event.state.value}"
                    ),
                )
            )

        # Initialize context
        if event.context is None or not isinstance(event.context, dict):
            event.context = {}
        context: JSONDict = cast(JSONDict, event.context)

        if not isinstance(event.payload, dict):
            event.payload = {}

        processing_ctx_raw = context.get("processing")
        if processing_ctx_raw is None or not isinstance(processing_ctx_raw, dict):
            processing_ctx_raw = {}
            context["processing"] = processing_ctx_raw
        processing_ctx: JSONDict = cast(JSONDict, processing_ctx_raw)

        # Lock state
        if event.state == EventState.PENDING:
            lock_result = transition_event(event, EventState.PROCESSING)
            if lock_result.is_err():
                return Err(lock_result.unwrap_err())
        elif event.state == EventState.TEMPORAL_ERROR:
            lock_result = transition_event(event, EventState.RETRYING)
            if lock_result.is_err():
                return Err(lock_result.unwrap_err())

        processing_ctx.setdefault("started_at", datetime.now(UTC).isoformat())

        # Persist lock
        save_lock = await self.uow.events.save(event)
        if save_lock.is_err():
            return Err(save_lock.unwrap_err())
        await self.uow.commit()

        # Get processor
        processor = self.processor_registry.get(event.name)
        processing_ctx["processor"] = processor.__class__.__name__

        # Process with retries
        return await self._process_with_retries(event, processor, processing_ctx, context)

    def _should_retry_exception(
        self, exc: BaseException, processor: IEventProcessor
    ) -> bool:
        """Determine if exception should trigger retry.

        TRANSIENT errors → retry
        PERMANENT errors → no retry
        """
        if isinstance(exc, RetryError):
            last_exc = exc.last_attempt.exception()
            if last_exc is not None:
                error_type = processor.classify_error(last_exc)
                return error_type == ErrorType.TRANSIENT
        else:
            error_type = processor.classify_error(exc)
            return error_type == ErrorType.TRANSIENT
        return False

    async def _handle_retry_exhausted(
        self,
        exc: RetryError,
        processor: IEventProcessor,
        processing_ctx: JSONDict,
        context: JSONDict,
    ) -> Result[ProcessEventResult, ErrorDetail]:
        """Handle case when all retry attempts are exhausted."""
        last_exc = exc.last_attempt.exception()
        error_type = processor.classify_error(
            last_exc if last_exc else Exception("Unknown error")
        )
        processing_ctx["last_error"] = str(last_exc) if last_exc else "Unknown"
        processing_ctx["last_error_type"] = error_type.value
        processing_ctx["attempts"] = self.max_attempts

        self._record_error(
            context,
            str(last_exc) if last_exc else "Unknown error",
            processor,
        )

        return Err(
            ErrorDetail(
                error=ErrorCatalog.RUNTIME_FAILED.value,
                detail=f"Failed after {self.max_attempts} attempts: {str(last_exc) if last_exc else 'Unknown error'}",
                metadata={"error_type": error_type.value},
            )
        )

    async def _handle_unrecoverable_error(
        self,
        exc: BaseException,
        processor: IEventProcessor,
        processing_ctx: JSONDict,
        context: JSONDict,
    ) -> Result[ProcessEventResult, ErrorDetail]:
        """Handle unrecoverable error (permanent error on first attempt)."""
        error_type = processor.classify_error(exc)
        processing_ctx["last_error"] = str(exc)
        processing_ctx["last_error_type"] = error_type.value

        self._record_error(context, str(exc), processor)

        return Err(
            ErrorDetail(
                error=ErrorCatalog.RUNTIME_FAILED.value,
                detail=str(exc),
                metadata={"error_type": error_type.value},
            )
        )

    async def _handle_success_result(
        self,
        event: Event,
        proc_result: ProcessorResult,
        processing_ctx: JSONDict,
    ) -> Result[ProcessEventResult, ErrorDetail]:
        """Handle successful processor result."""
        success_result = transition_event(event, EventState.COMPLETED)
        if success_result.is_err():
            return Err(success_result.unwrap_err())

        event.result = self._build_result(proc_result.data)
        processing_ctx["completed_at"] = datetime.now(UTC).isoformat()

        saved = await self.uow.events.save(event)
        if saved.is_err():
            return Err(saved.unwrap_err())
        await self.uow.commit()
        return Ok(self._as_output(saved.unwrap()))

    async def _handle_pending_callback_result(
        self,
        event: Event,
        proc_result: ProcessorResult,
        processing_ctx: JSONDict,
    ) -> Result[ProcessEventResult, ErrorDetail]:
        """Handle processor result with pending callback."""
        processing_ctx["callback_subject"] = proc_result.callback_subject
        if proc_result.metadata:
            processing_ctx["metadata"] = proc_result.metadata
        processing_ctx["pending_callback_at"] = datetime.now(UTC).isoformat()

        saved = await self.uow.events.save(event)
        if saved.is_err():
            return Err(saved.unwrap_err())
        await self.uow.commit()
        return Ok(self._as_output(saved.unwrap()))

    async def _handle_failed_result(
        self,
        event: Event,
        proc_result: ProcessorResult,
        context: JSONDict,
        processor: IEventProcessor,
    ) -> Result[ProcessEventResult, ErrorDetail]:
        """Handle processor failed result."""
        failure_result = transition_event(event, EventState.FAILED)
        if failure_result.is_err():
            return Err(failure_result.unwrap_err())

        self._record_error(context, proc_result.error or "Processor failed", processor)
        saved = await self.uow.events.save(event)
        if saved.is_err():
            return Err(saved.unwrap_err())
        await self.uow.commit()
        return Err(
            ErrorDetail(
                error=ErrorCatalog.RUNTIME_FAILED.value,
                detail=proc_result.error or "Processor failed",
            )
        )

    async def _process_with_retries(
        self,
        event: Event,
        processor: IEventProcessor,
        processing_ctx: JSONDict,
        context: JSONDict,
    ) -> Result[ProcessEventResult, ErrorDetail]:
        """Execute processor with exponential backoff retries.

        Retries only on TRANSIENT errors. PERMANENT errors fail immediately.
        Complexity: O(1) - delegates all branching to specialized handlers.
        """
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_exponential(multiplier=0.1, min=0.1, max=2.0),
                retry=retry_if_exception(
                    lambda exc: self._should_retry_exception(exc, processor)
                ),
                reraise=True,
            ):
                with attempt:
                    proc_result = await processor.process(event)
        except RetryError as exc:
            return await self._handle_retry_exhausted(
                exc, processor, processing_ctx, context
            )
        except BaseException as exc:  # noqa: BLE001
            return await self._handle_unrecoverable_error(
                exc, processor, processing_ctx, context
            )

        # Delegate result handling to specialized methods
        if proc_result.status == ProcessorResultStatus.SUCCESS:
            return await self._handle_success_result(event, proc_result, processing_ctx)

        if proc_result.status == ProcessorResultStatus.PENDING_CALLBACK:
            return await self._handle_pending_callback_result(
                event, proc_result, processing_ctx
            )

        # FAILED status
        return await self._handle_failed_result(event, proc_result, context, processor)

    def _build_result(self, data: dict[str, object] | None) -> EventResultStructure:
        payload: JSONDict = cast(JSONDict, data or {})
        return {"payload": payload}

    def _record_error(
        self, context: JSONDict, message: str, processor: IEventProcessor
    ) -> None:
        error_ctx_raw = context.get("error")
        if error_ctx_raw is None or not isinstance(error_ctx_raw, dict):
            error_ctx_raw = {}
            context["error"] = error_ctx_raw
        error_ctx: JSONDict = cast(JSONDict, error_ctx_raw)
        error_ctx["message"] = message
        error_ctx["processor"] = processor.__class__.__name__
        error_ctx["occurred_at"] = datetime.now(UTC).isoformat()

    def _as_output(self, event: Event) -> ProcessEventResult:
        return ProcessEventResult(
            id=event.id,
            name=event.name,
            state=event.state,
            external_uuid=event.external_uuid,
            payload=event.payload,
            context=event.context,
            result=event.result,
        )
