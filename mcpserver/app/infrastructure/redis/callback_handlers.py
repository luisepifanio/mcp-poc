"""
Callback handlers for long-running async processors.

Unified handler for all task callbacks via Redis Streams.
Listens on dynamic "event-result-{event_id}" streams.
"""

import logging
from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any, cast

from faststream import Context
from faststream.redis import RedisMessage

from app.core.entities import EventResultStructure, EventState, JSONDict
from app.infrastructure.db.unit_of_work import AsyncSQLAlchemyUnitOfWork
from app.infrastructure.processors import TaskCallbackPayload

logger = logging.getLogger(__name__)


async def handle_task_callback(
    body: TaskCallbackPayload,
    msg: RedisMessage,
    session: Any = Context("session"),
) -> None:
    """
    Unified callback handler for all long-running processors.

    Listens on: "event-result-*" (dynamic per-event topics)
    Payload: TaskCallbackPayload (Pydantic validated)

    Updates event state based on callback status:
    - status="success": PROCESSING → COMPLETED
    - status="failed": PROCESSING → FAILED (no retry)

    Args:
        body: TaskCallbackPayload with event_id, status, result/error
        msg: Redis message for ack/nack
        session: SQLAlchemy AsyncSession injected by FastStream

    Note:
        This handler is called per event callback. It's automatically
        registered for "event-result-*" stream by the broker.
    """
    try:
        event_id = body.event_id
        status = body.status

        logger.info(
            f"Task callback received for event {event_id}: {status}",
            extra={
                "event_id": str(event_id),
                "status": status,
                "has_error": body.error is not None,
            },
        )

        # Use existing transaction context from handler
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            # Load event
            event_result = await uow.events.getOne(event_id)
            if event_result.is_err():
                logger.error(f"Event {event_id} not found for callback")
                await msg.nack()
                return

            event = event_result.unwrap()

            # Ensure context is mutable mapping
            if not isinstance(event.context, MutableMapping):
                event.context = {}
            context: JSONDict = event.context
            event.context = context

            # Verify state (must be PROCESSING with callback metadata)
            if event.state != EventState.PROCESSING:
                logger.warning(
                    f"Event {event_id} not in PROCESSING state for callback",
                    extra={"event_state": event.state.value},
                )
                await msg.ack()  # Don't reprocess
                return

            # Update based on callback status
            if status == "success":
                # Success: Transition PROCESSING → COMPLETED
                event.state = EventState.COMPLETED
                if body.result:
                    event.result = cast(EventResultStructure, {"payload": body.result})

                # Update processing metadata
                processing_ctx_raw = context.get("processing")
                if not isinstance(processing_ctx_raw, MutableMapping):
                    processing_ctx_raw = {}
                    context["processing"] = processing_ctx_raw
                processing_ctx: JSONDict = processing_ctx_raw
                processing_ctx["completed_at"] = datetime.now(UTC).isoformat()

                # Calculate duration if started_at available
                started_at_value = processing_ctx.get("started_at")
                if isinstance(started_at_value, str):
                    try:
                        started = datetime.fromisoformat(started_at_value)
                        duration_ms = int(
                            (datetime.now(UTC) - started).total_seconds() * 1000
                        )
                        processing_ctx["duration_ms"] = duration_ms
                    except Exception:
                        pass  # Unable to calculate, skip

                # Record callback reception
                callback_ctx_raw = context.get("callback")
                if not isinstance(callback_ctx_raw, MutableMapping):
                    callback_ctx_raw = {}
                    context["callback"] = callback_ctx_raw
                success_callback_ctx: JSONDict = callback_ctx_raw
                success_callback_ctx["received_at"] = datetime.now(UTC).isoformat()
                success_callback_ctx["status"] = "success"
                if body.metadata:
                    success_callback_ctx["metadata"] = cast(JSONDict, body.metadata)

                logger.info(f"Event {event_id} completed via callback")

            else:
                # Failed: Transition PROCESSING → FAILED (no retry for task failures)
                event.state = EventState.FAILED

                # Record error
                error_ctx_raw = context.get("error")
                if not isinstance(error_ctx_raw, MutableMapping):
                    error_ctx_raw = {}
                    context["error"] = error_ctx_raw
                error_ctx: JSONDict = error_ctx_raw
                error_ctx["type"] = "task_failed"
                error_ctx["message"] = body.error or "Task failed"
                error_ctx["occurred_at"] = datetime.now(UTC).isoformat()

                # Record callback reception
                callback_ctx_raw = context.get("callback")
                if not isinstance(callback_ctx_raw, MutableMapping):
                    callback_ctx_raw = {}
                    context["callback"] = callback_ctx_raw
                failure_callback_ctx: JSONDict = callback_ctx_raw
                failure_callback_ctx["received_at"] = datetime.now(UTC).isoformat()
                failure_callback_ctx["status"] = "failed"
                if body.metadata:
                    failure_callback_ctx["metadata"] = cast(JSONDict, body.metadata)

                logger.error(
                    f"Event {event_id} failed via callback: {body.error}",
                    extra={"event_id": str(event_id), "error": body.error},
                )

            # Save event with transitions and context
            save_result = await uow.events.save(event)
            if save_result.is_err():
                logger.error(
                    f"Failed to save event {event_id} after callback",
                    extra={"event_id": str(event_id)},
                )
                await msg.nack()
                return

            # Success: ack message
            await msg.ack()
            logger.info(f"Event {event_id} callback processed successfully")

    except Exception as e:
        logger.error(
            f"Unexpected error in task callback handler: {e}",
            exc_info=True,
            extra={"error_type": type(e).__name__},
        )
        await msg.nack()
