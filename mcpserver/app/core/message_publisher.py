"""
Message publisher abstraction for event routing.

Used for publishing events that require external notification:
- FAILED events (permanent failures): sent to DLQ for manual review
- EXHAUSTED events (retry limit exceeded): sent to DLQ for manual review
- SUCCESS events (optional): can publish for analytics/logging

Design:
- Abstract IMessagePublisher interface (ABC)
- Concrete RedisMessagePublisher implementation
- Dependency injection pattern (injected into handlers)
"""

from abc import ABC, abstractmethod
from typing import Any

from .entities import Event


class IMessagePublisher(ABC):
    """
    Abstract message publisher interface.

    Responsible for publishing important events to external systems
    (DLQ, topic queues, webhooks, etc.) for monitoring and manual intervention.
    """

    @abstractmethod
    async def publish_failed_event(self, event: Event, error: str) -> None:
        """
        Publish an event that failed permanently.

        Called when an event transitions to FAILED state (no retry).

        Args:
            event: Event that failed
            error: Error message explaining the failure
        """

    @abstractmethod
    async def publish_exhausted_event(self, event: Event, error: str) -> None:
        """
        Publish an event that exhausted all retries.

        Called when an event transitions to EXHAUSTED state.

        Args:
            event: Event that exhausted retries
            error: Final error message
        """

    @abstractmethod
    async def publish_success_event(
        self, event: Event, result: dict[str, Any] | None = None
    ) -> None:
        """
        Publish a successfully processed event (optional).

        Can be used for analytics, logging, or downstream processing.

        Args:
            event: Event that succeeded
            result: Optional result data from processing
        """
