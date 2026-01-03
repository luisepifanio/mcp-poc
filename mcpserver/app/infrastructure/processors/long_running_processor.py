"""
Long-running task processors for async processing with callbacks.

Processors for tasks that take time (web scraping, ML inference, batch processing).
These processors publish tasks to external workers and return PENDING_CALLBACK.
Results are delivered via callbacks to "event-result-{event_id}".
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.processors import (
    IEventProcessor,
    ProcessorResult,
    ProcessorResultStatus,
    RetryConfig,
)

logger = logging.getLogger(__name__)


class LongRunningTaskProcessor(IEventProcessor):
    """
    Base class for long-running task processors.

    Subclasses define:
    - task_subject: Redis topic where task is published (e.g., "scraping-task-subject")
    - Task payload format (if specific to processor type)

    Flow:
    1. Validate task params from event.payload
    2. Publish to task_subject (external worker subscribes)
    3. Return PENDING_CALLBACK with callback_subject="event-result-{event_id}"
    4. Event state transitions to PROCESSING
    5. External worker processes and publishes callback to callback_subject
    6. handle_task_callback updates event state to COMPLETED/FAILED
    """

    def __init__(self, broker: Any, task_subject: str):
        """
        Initialize long-running task processor.

        Args:
            broker: FastStream RedisBroker for publishing tasks
            task_subject: Redis topic for publishing tasks (e.g., "scraping-task-subject")
        """
        self.broker = broker
        self.task_subject = task_subject
        self.logger = logger

    async def process(self, event: Any) -> ProcessorResult:
        """
        Publish task and return PENDING_CALLBACK.

        Subclasses should override if they need custom task payload format.

        Args:
            event: Event entity with task parameters in event.payload

        Returns:
            ProcessorResult with PENDING_CALLBACK status and callback_subject

        Raises:
            ValueError: If task params validation fails
        """
        callback_subject = f"event-result-{event.id}"

        # Build task payload
        task_payload = {
            "event_id": str(event.id),
            "task_params": event.payload or {},
            "callback_subject": callback_subject,
        }

        self.logger.info(
            f"Publishing task to {self.task_subject}",
            extra={
                "event_id": str(event.id),
                "task_subject": self.task_subject,
                "callback_subject": callback_subject,
            },
        )

        # Publish task to external worker
        try:
            await self.broker.publish(
                task_payload,
                stream=self.task_subject,
            )
        except Exception as e:
            self.logger.error(
                f"Failed to publish task: {e}",
                extra={
                    "event_id": str(event.id),
                    "task_subject": self.task_subject,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

        return ProcessorResult(
            status=ProcessorResultStatus.PENDING_CALLBACK,
            callback_subject=callback_subject,
            metadata={
                "task_subject": self.task_subject,
                "published_at": datetime.now(UTC).isoformat(),
            },
        )

    def get_retry_config(self) -> RetryConfig:
        """
        No retries for long-running task processors.

        If task fails, it's handled by callback (not by retry logic).
        The external worker is responsible for task retry logic.

        Returns:
            RetryConfig with max_attempts=1 (no retries)
        """
        return RetryConfig(
            max_attempts=1,
            initial_backoff=0.0,
            max_backoff=0.0,
            backoff_multiplier=1.0,
            fast_retry_count=0,
            fast_retry_delay=0.0,
        )


class ScrapingProcessor(LongRunningTaskProcessor):
    """
    Processor for web scraping tasks.

    Publishes scraping tasks to "scraping-task-subject" for external workers.

    Expected event.payload format:
    {
        "url": "https://example.com",
        "selector": ".product-item",
        ...other scraping params...
    }

    Task callback expected on: "event-result-{event_id}"
    """

    def __init__(self, broker: Any):
        """Initialize scraping processor."""
        super().__init__(broker, task_subject="scraping-task-subject")


class MlInferenceProcessor(LongRunningTaskProcessor):
    """
    Processor for ML inference tasks.

    Publishes inference tasks to "ml-inference-subject" for external workers.

    Expected event.payload format:
    {
        "model_id": "model_v2.1",
        "input": {...model input...},
        ...other inference params...
    }

    Task callback expected on: "event-result-{event_id}"
    """

    def __init__(self, broker: Any):
        """Initialize ML inference processor."""
        super().__init__(broker, task_subject="ml-inference-subject")


class BatchExportProcessor(LongRunningTaskProcessor):
    """
    Processor for batch export tasks.

    Publishes batch tasks to "batch-export-subject" for external workers.

    Expected event.payload format:
    {
        "query": {...},
        "format": "csv|json|parquet",
        "destination": "s3://bucket/path",
        ...other export params...
    }

    Task callback expected on: "event-result-{event_id}"
    """

    def __init__(self, broker: Any):
        """Initialize batch export processor."""
        super().__init__(broker, task_subject="batch-export-subject")
