"""
Callback handlers for long-running async processors.

Unified handler for all task callbacks via Redis Streams.
Listens on dynamic "event-result-{event_id}" streams.
"""

import logging
from datetime import UTC, datetime

from faststream import Context
from faststream.redis import RedisMessage

from app.infrastructure.db.unit_of_work import AsyncSQLAlchemyUnitOfWork
from app.infrastructure.processors import TaskCallbackPayload

logger = logging.getLogger(__name__)


async def handle_task_callback(
    body: TaskCallbackPayload,
    msg: RedisMessage,
    session=Context("session"),
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
            event_result = await uow.events.get_by_id(event_id)
            if event_result.is_err():
                logger.error(f"Event {event_id} not found for callback")
                await msg.nack()
                return

            event = event_result.unwrap()

            # Verify state (must be PROCESSING with callback metadata)
            from app.core.entities import EventState

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
                    event.result = body.result

                # Update processing metadata
                if "processing" not in event.context:
                    event.context["processing"] = {}
                event.context["processing"]["completed_at"] = datetime.now(
                    UTC
                ).isoformat()

                # Calculate duration if started_at available
                if "started_at" in event.context.get("processing", {}):
                    try:
                        started = datetime.fromisoformat(
                            event.context["processing"]["started_at"]
                        )
                        duration_ms = int(
                            (datetime.now(UTC) - started).total_seconds() * 1000
                        )
                        event.context["processing"]["duration_ms"] = duration_ms
                    except Exception:
                        pass  # Unable to calculate, skip

                # Record callback reception
                if "callback" not in event.context:
                    event.context["callback"] = {}
                event.context["callback"]["received_at"] = datetime.now(
                    UTC
                ).isoformat()
                event.context["callback"]["status"] = "success"
                if body.metadata:
                    event.context["callback"]["metadata"] = body.metadata

                logger.info(f"Event {event_id} completed via callback")

            else:
                # Failed: Transition PROCESSING → FAILED (no retry for task failures)
                event.state = EventState.FAILED

                # Record error
                if "error" not in event.context:
                    event.context["error"] = {}
                event.context["error"]["type"] = "task_failed"
                event.context["error"]["message"] = body.error or "Task failed"
                event.context["error"]["occurred_at"] = datetime.now(
                    UTC
                ).isoformat()

                # Record callback reception
                if "callback" not in event.context:
                    event.context["callback"] = {}
                event.context["callback"]["received_at"] = datetime.now(
                    UTC
                ).isoformat()
                event.context["callback"]["status"] = "failed"
                if body.metadata:
                    event.context["callback"]["metadata"] = body.metadata

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
