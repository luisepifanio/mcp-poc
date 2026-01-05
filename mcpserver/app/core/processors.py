"""
Event processor abstractions and types.

This module defines the processor pattern:
- IEventProcessor: ABC for all event processors
- ProcessorResult: Result of processor execution
- ErrorType: Error classification (TRANSIENT, PERMANENT, RATE_LIMIT)
- RetryConfig: Retry configuration per processor type
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorType(str, Enum):
    """Error classification for retry strategy."""

    TRANSIENT = "transient"  # Should retry (infra failures)
    PERMANENT = "permanent"  # Should not retry (validation errors)
    RATE_LIMIT = "rate_limit"  # Should retry with longer backoff


class ProcessorResultStatus(str, Enum):
    """Status of processor execution."""

    SUCCESS = "success"  # Sync processors completed successfully
    PENDING_CALLBACK = "pending_callback"  # Async processor published task
    FAILED = "failed"  # Processor failed (should not retry)


@dataclass
class RetryConfig:
    """Retry configuration for a processor type."""

    max_attempts: int  # Total number of retry attempts
    initial_backoff: float  # Initial backoff in seconds (for exponential backoff)
    max_backoff: float  # Maximum backoff in seconds
    backoff_multiplier: float  # Multiplier for exponential backoff
    fast_retry_count: int = 2  # Number of fast retries (100ms)
    fast_retry_delay: float = 0.1  # Delay for fast retries (0.1s = 100ms)


@dataclass
class ProcessorResult:
    """Result of processor execution."""

    status: ProcessorResultStatus
    data: dict[str, Any] | None = None  # Data returned by processor
    error: str | None = None  # Error message if failed
    callback_subject: str | None = None  # Redis topic for async callback
    metadata: dict[str, Any] = field(default_factory=dict)  # Processor-specific metadata


class IEventProcessor(ABC):
    """
    Abstract base class for all event processors.

    Each processor implementation handles a specific event type:
    - ApiCallProcessor: HTTP/REST calls
    - GrpcProcessor: gRPC calls
    - LocalUseCaseProcessor: Local async function calls
    - LongRunningTaskProcessor: Long-running async tasks with callbacks
    """

    @abstractmethod
    async def process(self, event: Any) -> ProcessorResult:
        """
        Process an event.

        Args:
            event: Event entity to process

        Returns:
            ProcessorResult with status and optional data/callback_subject

        Raises:
            Exception: May raise exceptions for classification by classify_error()
        """
        pass

    @abstractmethod
    def get_retry_config(self) -> RetryConfig:
        """
        Get retry configuration for this processor.

        Returns:
            RetryConfig with max_attempts, backoff settings, etc.
        """
        pass

    def classify_error(self, exc: BaseException) -> ErrorType:
        """
        Classify an error to determine retry strategy.

        Default implementation:
        - ValidationError, ValueError → PERMANENT (no retry)
        - ConnectionError, TimeoutError → TRANSIENT (retry)
        - Others → PERMANENT (default to safe no-retry)

        Subclasses can override for processor-specific classification.

        Args:
            exc: Exception raised during processing

        Returns:
            ErrorType indicating retry behavior
        """
        from pydantic import ValidationError

        if isinstance(exc, (ValidationError, ValueError)):
            return ErrorType.PERMANENT
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return ErrorType.TRANSIENT
        return ErrorType.PERMANENT
