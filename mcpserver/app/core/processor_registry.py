"""
Processor registry for mapping event names to processor implementations.

The registry uses a NoOpProcessor as fallback for unregistered event types,
enabling automatic detection and monitoring of new events.
"""

import logging
from typing import Any

from app.core.processors import (
    ErrorType,
    IEventProcessor,
    ProcessorResult,
    RetryConfig,
)

logger = logging.getLogger(__name__)


class NoOpProcessor(IEventProcessor):
    """
    Default processor for unregistered event types.

    Purpose: Detect and monitor new event types that haven't been
    added to the processor catalog. Marks events as FAILED with
    structured logging for observability.

    Usage:
    - Automatically returned by ProcessorRegistry.get() when event_name not found
    - Logs warning with event details for manual review
    - Marks event as FAILED (PERMANENT error, no retry)
    """

    async def process(self, event: Any) -> ProcessorResult:
        """
        Handle unregistered event type.

        Logs warning and raises ValueError (classified as PERMANENT).
        """
        event_name = getattr(event, "name", "unknown")
        event_id = getattr(event, "id", "unknown")
        payload_keys = (
            list(getattr(event, "payload", {}).keys())
            if hasattr(event, "payload") and event.payload
            else []
        )

        logger.warning(
            "NoOpProcessor: Event without registered processor",
            extra={
                "event_id": str(event_id),
                "event_name": event_name,
                "payload_keys": payload_keys,
            },
        )

        raise ValueError(
            f"No processor registered for event type: {event_name}. "
            "Add to ProcessorRegistry or update catalog configuration."
        )

    def get_retry_config(self) -> RetryConfig:
        """No retries for missing processor (permanent error)."""
        return RetryConfig(
            max_attempts=1,
            initial_backoff=0.0,
            max_backoff=0.0,
            backoff_multiplier=1.0,
            fast_retry_count=0,
            fast_retry_delay=0.0,
        )

    def classify_error(self, exc: Exception) -> ErrorType:
        """Always permanent - missing processor is not retryable."""
        return ErrorType.PERMANENT


class ProcessorRegistry:
    """
    Registry for mapping event types to processor implementations.

    Features:
    - Register processors for specific event names
    - Fallback to NoOpProcessor for unregistered events
    - Logging for new event type detection
    - Check if processor explicitly registered (excludes NoOp)
    """

    def __init__(self) -> None:
        """Initialize empty registry with NoOpProcessor as fallback."""
        self._processors: dict[str, IEventProcessor] = {}
        self._noop = NoOpProcessor()

    def register(self, event_name: str, processor: IEventProcessor) -> None:
        """
        Register a processor for an event type.

        Args:
            event_name: Event name/type to handle
            processor: IEventProcessor implementation
        """
        logger.info(f"Registered processor for event type: {event_name}")
        self._processors[event_name] = processor

    def get(self, event_name: str) -> IEventProcessor:
        """
        Get processor for event type.

        Returns explicit processor if registered, otherwise returns
        NoOpProcessor and logs warning (automatic detection of new events).

        Args:
            event_name: Event name/type

        Returns:
            IEventProcessor instance (explicit or NoOpProcessor)
        """
        processor = self._processors.get(event_name)

        if processor is None:
            logger.warning(
                f"Processor not found for event type: {event_name}, "
                f"using NoOpProcessor (will mark as FAILED)",
                extra={"event_name": event_name},
            )
            return self._noop

        return processor

    def has(self, event_name: str) -> bool:
        """
        Check if explicit processor registered (excludes NoOp fallback).

        Args:
            event_name: Event name/type

        Returns:
            True if explicit processor registered, False otherwise
        """
        return event_name in self._processors

    def list_registered(self) -> list[str]:
        """
        List all explicitly registered event types.

        Returns:
            List of event names with explicit processors
        """
        return list(self._processors.keys())


# Global instance
processor_registry = ProcessorRegistry()


def setup_processors(broker: Any = None, uow: Any = None) -> None:
    """
    Setup and register all processors.

    Called during application startup. Processors may require broker
    (for publishing tasks) or uow (for DB access).

    Args:
        broker: FastStream RedisBroker instance (for long-running processors)
        uow: IUnitOfWork instance (for local use case processors)
    """
    # TODO: Implement concrete processors
    # from app.infrastructure.processors.sync_processors import (
    #     ApiCallProcessor,
    #     GrpcProcessor,
    #     LocalUseCaseProcessor,
    # )
    # from app.infrastructure.processors.long_running_processor import (
    #     ScrapingProcessor,
    #     MlInferenceProcessor,
    # )

    # Sync processors (will be registered here)
    # processor_registry.register("api_call", ApiCallProcessor())
    # processor_registry.register("grpc_call", GrpcProcessor())
    # processor_registry.register("local_usecase", LocalUseCaseProcessor(uow))

    # Async long-running processors
    # processor_registry.register("scraping_task", ScrapingProcessor(broker))
    # processor_registry.register("ml_inference", MlInferenceProcessor(broker))

    logger.info(
        f"Processor registry initialized with {len(processor_registry.list_registered())} "
        "explicit processors"
    )
