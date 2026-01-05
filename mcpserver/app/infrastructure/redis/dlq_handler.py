"""
DLQ (Dead Letter Queue) handler for event monitoring.

Subscribes to dlq-subject stream to receive and log events that:
- Failed permanently (FAILED state)
- Exhausted all retries (EXHAUSTED state)

Logging mode: Structured logging for monitoring/alerting.
(No persistence/acknowledgment yet - can be added later)
"""

import logging
from typing import Any

from faststream import AckPolicy
from faststream.redis import RedisBroker
from faststream.redis.annotations import RedisMessage

logger = logging.getLogger(__name__)


def setup_dlq_subscriber(broker: RedisBroker) -> Any:
    """
    Setup DLQ subscriber decorator.

    Args:
        broker: FastStream RedisBroker instance

    Returns:
        Decorated function for subscribing to DLQ messages
    """
    return broker.subscriber(
        "dlq-subject",
        ack_policy=AckPolicy.MANUAL,  # Manual ack
    )


async def handle_dlq_message(
    body: dict[str, Any],
    msg: RedisMessage,
) -> None:
    """
    Handle Dead Letter Queue message.

    Logs structured information about events that require manual intervention.

    Message structure (from RedisMessagePublisher):
    {
        "event_id": str,
        "event_name": str,
        "external_uuid": str | None,
        "state": "failed" | "exhausted",
        "error": str,
        "timestamp": ISO datetime string,
        "type": "FAILED" | "EXHAUSTED",
        "payload": dict,
        "context": dict,
    }

    Args:
        body: Parsed message from DLQ stream
        msg: FastStream message metadata
    """
    try:
        event_id = body.get("event_id", "unknown")
        event_name = body.get("event_name", "unknown")
        state = body.get("state", "unknown")
        error_type = body.get("type", "UNKNOWN")
        error = body.get("error", "No error message")
        external_uuid = body.get("external_uuid")
        timestamp = body.get("timestamp")

        # Log structured information
        logger.warning(
            f"DLQ Event: {error_type} - {event_name} ({event_id})",
            extra={
                "event_id": event_id,
                "event_name": event_name,
                "external_uuid": external_uuid,
                "state": state,
                "type": error_type,
                "error": error,
                "timestamp": timestamp,
                "payload_keys": list(body.get("payload", {}).keys()),
                "context_keys": list(body.get("context", {}).keys()),
            },
        )

        # Per-type handling
        if error_type == "FAILED":
            logger.error(
                f"Event permanently failed: {event_name} ({event_id})",
                extra={
                    "event_id": event_id,
                    "error": error,
                },
            )
            # TODO: Could emit metric/alert here
            # metrics.counter("dlq.failed", tags={"event": event_name})

        elif error_type == "EXHAUSTED":
            logger.error(
                f"Event exhausted retries: {event_name} ({event_id})",
                extra={
                    "event_id": event_id,
                    "error": error,
                },
            )
            # TODO: Could emit different alert for exhausted
            # metrics.counter("dlq.exhausted", tags={"event": event_name})

        # Acknowledge message
        await msg.ack()
        logger.debug(f"DLQ message acknowledged: {event_id}")

    except Exception as exc:
        logger.error(
            f"Error processing DLQ message: {exc}",
            extra={"body": str(body), "error": str(exc)},
            exc_info=True,
        )
        # Negative ack for reprocessing
        await msg.nack()
