"""
Redis message publisher implementation.

Publishes important events (FAILED, EXHAUSTED) to DLQ streams for
monitoring and manual intervention.

Stream: dlq-subject
- Capture events that require manual action
- Structured logging with full event context
- No message loss (persisted in Redis Streams)
"""

import logging
from datetime import UTC, datetime
from typing import Any

from faststream.redis import RedisBroker

from app.core.entities import Event
from app.core.message_publisher import IMessagePublisher

logger = logging.getLogger(__name__)


class RedisMessagePublisher(IMessagePublisher):
    """
    Redis implementation of message publisher.

    Publishes important events to DLQ stream for monitoring.
    """

    def __init__(self, broker: RedisBroker, dlq_stream: str = "dlq-subject"):
        """
        Initialize Redis message publisher.

        Args:
            broker: FastStream RedisBroker instance
            dlq_stream: Stream name for DLQ (default: "dlq-subject")
        """
        self.broker = broker
        self.dlq_stream = dlq_stream
        self.logger = logger

    async def publish_failed_event(self, event: Event, error: str) -> None:
        """
        Publish event that failed permanently.

        Args:
            event: Event that failed
            error: Error message
        """
        message = {
            "event_id": str(event.id),
            "event_name": event.name,
            "external_uuid": str(event.external_uuid) if event.external_uuid else None,
            "state": event.state.value,
            "error": error,
            "timestamp": datetime.now(UTC).isoformat(),
            "type": "FAILED",
            "payload": event.payload,
            "context": event.context,
        }

        try:
            await self.broker.publish(
                message,
                stream=self.dlq_stream,
            )
            self.logger.info(
                f"Published FAILED event to DLQ: {event.id}",
                extra={
                    "event_id": str(event.id),
                    "event_name": event.name,
                    "dlq_stream": self.dlq_stream,
                },
            )
        except Exception as exc:
            self.logger.error(
                f"Failed to publish FAILED event to DLQ: {exc}",
                extra={
                    "event_id": str(event.id),
                    "event_name": event.name,
                    "error": str(exc),
                },
            )
            # Re-raise to be handled by caller
            raise

    async def publish_exhausted_event(self, event: Event, error: str) -> None:
        """
        Publish event that exhausted all retries.

        Args:
            event: Event that exhausted retries
            error: Final error message
        """
        message = {
            "event_id": str(event.id),
            "event_name": event.name,
            "external_uuid": str(event.external_uuid) if event.external_uuid else None,
            "state": event.state.value,
            "error": error,
            "timestamp": datetime.now(UTC).isoformat(),
            "type": "EXHAUSTED",
            "payload": event.payload,
            "context": event.context,
        }

        try:
            await self.broker.publish(
                message,
                stream=self.dlq_stream,
            )
            self.logger.warning(
                f"Published EXHAUSTED event to DLQ: {event.id}",
                extra={
                    "event_id": str(event.id),
                    "event_name": event.name,
                    "dlq_stream": self.dlq_stream,
                },
            )
        except Exception as exc:
            self.logger.error(
                f"Failed to publish EXHAUSTED event to DLQ: {exc}",
                extra={
                    "event_id": str(event.id),
                    "event_name": event.name,
                    "error": str(exc),
                },
            )
            raise

    async def publish_success_event(
        self, event: Event, result: dict[str, Any] | None = None
    ) -> None:
        """
        Publish successfully processed event (optional).

        Can be used for analytics, logging, or downstream processing.
        Does not use DLQ stream - implement separate analytics stream if needed.

        Args:
            event: Event that succeeded
            result: Optional result data
        """
        self.logger.debug(
            f"Event successfully processed: {event.id}",
            extra={
                "event_id": str(event.id),
                "event_name": event.name,
                "result_keys": list(result.keys()) if result else [],
            },
        )
        # Optional: Publish to analytics/success stream
        # For now, just log for observability
