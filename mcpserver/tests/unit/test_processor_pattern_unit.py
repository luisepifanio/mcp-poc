"""
Unit tests for processor pattern implementation.

Tests for:
- IEventProcessor ABC
- ProcessorRegistry with NoOpProcessor fallback
- Error classification
- ProcessorResult handling
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.entities import Event
from app.core.processor_registry import (
    NoOpProcessor,
    ProcessorRegistry,
    processor_registry,
)
from app.core.processors import (
    ErrorType,
    IEventProcessor,
    ProcessorResult,
    ProcessorResultStatus,
    RetryConfig,
)


class MockProcessor(IEventProcessor):
    """Mock processor for testing."""

    async def process(self, event: Event) -> ProcessorResult:
        """Return SUCCESS by default."""
        return ProcessorResult(
            status=ProcessorResultStatus.SUCCESS,
            data={"processed": True},
        )

    def get_retry_config(self) -> RetryConfig:
        """Return default retry config."""
        return RetryConfig(
            max_attempts=3,
            initial_backoff=0.1,
            max_backoff=1.0,
            backoff_multiplier=2.0,
        )


class MockFailingProcessor(IEventProcessor):
    """Mock processor that raises exception."""

    async def process(self, event: Event) -> ProcessorResult:
        """Raise validation error."""
        raise ValueError("Invalid input")

    def get_retry_config(self) -> RetryConfig:
        return RetryConfig(
            max_attempts=1,
            initial_backoff=0.0,
            max_backoff=0.0,
            backoff_multiplier=1.0,
        )


# ============================================================================
# ProcessorRegistry Tests
# ============================================================================


class TestProcessorRegistry:
    """Test ProcessorRegistry with NoOpProcessor fallback."""

    def test_registry_register_and_get(self):
        """Test registering and retrieving processor."""
        registry = ProcessorRegistry()
        processor = MockProcessor()

        registry.register("test_event", processor)

        retrieved = registry.get("test_event")
        assert retrieved is processor

    def test_registry_returns_noop_for_unregistered(self):
        """Test that unregistered event types return NoOpProcessor."""
        registry = ProcessorRegistry()

        processor = registry.get("unknown_event_type")

        assert isinstance(processor, NoOpProcessor)

    def test_registry_has_checks_explicit_only(self):
        """Test that has() only checks explicit registrations, not NoOp."""
        registry = ProcessorRegistry()
        processor = MockProcessor()

        registry.register("registered", processor)

        assert registry.has("registered") is True
        assert registry.has("unregistered") is False

    def test_registry_list_registered(self):
        """Test listing all registered event types."""
        registry = ProcessorRegistry()

        registry.register("event1", MockProcessor())
        registry.register("event2", MockProcessor())

        assert set(registry.list_registered()) == {"event1", "event2"}

    def test_registry_multiple_processors(self):
        """Test registry with multiple different processors."""
        registry = ProcessorRegistry()
        proc1 = MockProcessor()
        proc2 = MockFailingProcessor()

        registry.register("success_event", proc1)
        registry.register("fail_event", proc2)

        assert registry.get("success_event") is proc1
        assert registry.get("fail_event") is proc2


# ============================================================================
# NoOpProcessor Tests
# ============================================================================


class TestNoOpProcessor:
    """Test NoOpProcessor for unregistered event detection."""

    @pytest.mark.asyncio
    async def test_noop_processor_raises_on_process(self):
        """Test that NoOpProcessor raises ValueError."""
        processor = NoOpProcessor()
        event = Event(
            name="unknown_type",
            payload={},
            external_uuid=uuid4(),
        )

        with pytest.raises(ValueError, match="No processor registered"):
            await processor.process(event)

    def test_noop_processor_retry_config(self):
        """Test that NoOpProcessor has no-retry config."""
        processor = NoOpProcessor()

        config = processor.get_retry_config()

        assert config.max_attempts == 1
        assert config.initial_backoff == 0.0
        assert config.fast_retry_count == 0

    def test_noop_processor_classifies_as_permanent(self):
        """Test that NoOpProcessor classifies all errors as permanent."""
        processor = NoOpProcessor()

        error_type = processor.classify_error(ValueError("test"))

        assert error_type == ErrorType.PERMANENT


# ============================================================================
# Error Classification Tests
# ============================================================================


class TestErrorClassification:
    """Test error classification for retry strategy."""

    def test_classify_validation_error_as_permanent(self):
        """Test that ValidationError is classified as PERMANENT."""
        processor = MockProcessor()

        error_type = processor.classify_error(ValidationError.from_exception_data("test", []))

        assert error_type == ErrorType.PERMANENT

    def test_classify_value_error_as_permanent(self):
        """Test that ValueError is classified as PERMANENT."""
        processor = MockProcessor()

        error_type = processor.classify_error(ValueError("test"))

        assert error_type == ErrorType.PERMANENT

    def test_classify_connection_error_as_transient(self):
        """Test that ConnectionError is classified as TRANSIENT."""
        processor = MockProcessor()

        error_type = processor.classify_error(ConnectionError("test"))

        assert error_type == ErrorType.TRANSIENT

    def test_classify_timeout_error_as_transient(self):
        """Test that TimeoutError is classified as TRANSIENT."""
        processor = MockProcessor()

        error_type = processor.classify_error(TimeoutError("test"))

        assert error_type == ErrorType.TRANSIENT

    def test_classify_unknown_error_as_permanent(self):
        """Test that unknown errors default to PERMANENT."""
        processor = MockProcessor()

        error_type = processor.classify_error(RuntimeError("test"))

        assert error_type == ErrorType.PERMANENT


# ============================================================================
# ProcessorResult Tests
# ============================================================================


class TestProcessorResult:
    """Test ProcessorResult data class."""

    def test_processor_result_success(self):
        """Test ProcessorResult with SUCCESS status."""
        result = ProcessorResult(
            status=ProcessorResultStatus.SUCCESS,
            data={"key": "value"},
        )

        assert result.status == ProcessorResultStatus.SUCCESS
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_processor_result_pending_callback(self):
        """Test ProcessorResult with PENDING_CALLBACK status."""
        result = ProcessorResult(
            status=ProcessorResultStatus.PENDING_CALLBACK,
            callback_subject="event-result-123",
            metadata={"task_subject": "scraping-task-subject"},
        )

        assert result.status == ProcessorResultStatus.PENDING_CALLBACK
        assert result.callback_subject == "event-result-123"
        assert result.metadata["task_subject"] == "scraping-task-subject"

    def test_processor_result_failed(self):
        """Test ProcessorResult with FAILED status."""
        result = ProcessorResult(
            status=ProcessorResultStatus.FAILED,
            error="Processing failed",
        )

        assert result.status == ProcessorResultStatus.FAILED
        assert result.error == "Processing failed"


# ============================================================================
# Retry Configuration Tests
# ============================================================================


class TestRetryConfig:
    """Test RetryConfig for different processor types."""

    def test_retry_config_defaults(self):
        """Test RetryConfig with default values."""
        config = RetryConfig(
            max_attempts=3,
            initial_backoff=0.1,
            max_backoff=1.0,
            backoff_multiplier=2.0,
        )

        assert config.fast_retry_count == 2
        assert config.fast_retry_delay == 0.1

    def test_retry_config_custom_fast_retry(self):
        """Test RetryConfig with custom fast retry settings."""
        config = RetryConfig(
            max_attempts=5,
            initial_backoff=0.5,
            max_backoff=10.0,
            backoff_multiplier=1.5,
            fast_retry_count=3,
            fast_retry_delay=0.05,
        )

        assert config.fast_retry_count == 3
        assert config.fast_retry_delay == 0.05

    def test_retry_config_no_retry(self):
        """Test RetryConfig with no retries (max_attempts=1)."""
        config = RetryConfig(
            max_attempts=1,
            initial_backoff=0.0,
            max_backoff=0.0,
            backoff_multiplier=1.0,
            fast_retry_count=0,
            fast_retry_delay=0.0,
        )

        assert config.max_attempts == 1
        assert config.initial_backoff == 0.0


# ============================================================================
# Processor Implementation Tests
# ============================================================================


class TestMockProcessor:
    """Test mock processor implementation."""

    @pytest.mark.asyncio
    async def test_mock_processor_success(self):
        """Test mock processor returning SUCCESS."""
        processor = MockProcessor()
        event = Event(
            name="test",
            payload={},
            external_uuid=uuid4(),
        )

        result = await processor.process(event)

        assert result.status == ProcessorResultStatus.SUCCESS
        assert result.data == {"processed": True}

    def test_mock_processor_retry_config(self):
        """Test mock processor retry configuration."""
        processor = MockProcessor()

        config = processor.get_retry_config()

        assert config.max_attempts == 3
        assert config.initial_backoff == 0.1


# ============================================================================
# Global Registry Tests
# ============================================================================


def test_global_processor_registry_instance():
    """Test that global processor_registry is initialized."""
    assert processor_registry is not None
    assert isinstance(processor_registry, ProcessorRegistry)


def test_global_registry_returns_noop_for_unknown():
    """Test that global registry returns NoOp for unknown events."""
    processor = processor_registry.get("unknown_event_xyz")

    assert isinstance(processor, NoOpProcessor)
