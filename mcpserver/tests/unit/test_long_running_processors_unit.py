"""
Unit tests for callback payloads and long-running processors.

Tests for:
- TaskCallbackPayload Pydantic model
- Long-running task processor implementations
- Task publishing and callback flow
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.entities import Event
from app.core.processors import ProcessorResultStatus
from app.infrastructure.processors import (
    MlInferenceCallbackPayload,
    ScrapingTaskCallbackPayload,
    TaskCallbackPayload,
)
from app.infrastructure.processors.long_running_processor import (
    BatchExportProcessor,
    LongRunningTaskProcessor,
    MlInferenceProcessor,
    ScrapingProcessor,
)

# ============================================================================
# TaskCallbackPayload Tests
# ============================================================================


class TestTaskCallbackPayload:
    """Test TaskCallbackPayload Pydantic model."""

    def test_payload_success_status(self):
        """Test TaskCallbackPayload with success status."""
        event_id = uuid4()
        payload = TaskCallbackPayload(
            event_id=event_id,
            status="success",
            result={"data": "result"},
        )

        assert payload.event_id == event_id
        assert payload.status == "success"
        assert payload.result == {"data": "result"}
        assert payload.error is None

    def test_payload_failed_status(self):
        """Test TaskCallbackPayload with failed status."""
        event_id = uuid4()
        payload = TaskCallbackPayload(
            event_id=event_id,
            status="failed",
            error="Task failed",
        )

        assert payload.event_id == event_id
        assert payload.status == "failed"
        assert payload.error == "Task failed"
        assert payload.result is None

    def test_payload_with_metadata(self):
        """Test TaskCallbackPayload with metadata."""
        event_id = uuid4()
        metadata = {"duration_ms": 5000, "custom": "value"}
        payload = TaskCallbackPayload(
            event_id=event_id,
            status="success",
            metadata=metadata,
        )

        assert payload.metadata == metadata

    def test_payload_invalid_status(self):
        """Test TaskCallbackPayload rejects invalid status."""
        event_id = uuid4()

        with pytest.raises(ValidationError):
            TaskCallbackPayload(
                event_id=event_id,
                status="unknown",  # Invalid
            )

    def test_payload_allows_extra_fields(self):
        """Test TaskCallbackPayload allows extra fields (extra='allow')."""
        event_id = uuid4()

        # Extra fields should be allowed
        payload = TaskCallbackPayload(
            event_id=event_id,
            status="success",
            extra_field="allowed",  # Not in schema
        )

        assert payload.event_id == event_id


# ============================================================================
# ScrapingTaskCallbackPayload Tests
# ============================================================================


class TestScrapingTaskCallbackPayload:
    """Test scraping-specific callback payload."""

    def test_scraping_payload_success(self):
        """Test scraping callback with success."""
        event_id = uuid4()
        metadata = {
            "url": "https://example.com",
            "selector_count": 42,
            "duration_ms": 5000,
        }
        payload = ScrapingTaskCallbackPayload(
            event_id=event_id,
            status="success",
            result={"selectors": [{"text": "..."}]},
            metadata=metadata,
        )

        assert payload.event_id == event_id
        assert payload.status == "success"
        assert payload.metadata["url"] == "https://example.com"
        assert payload.metadata["selector_count"] == 42

    def test_scraping_payload_inherits_task_callback(self):
        """Test that ScrapingTaskCallbackPayload inherits TaskCallbackPayload."""
        event_id = uuid4()
        payload = ScrapingTaskCallbackPayload(
            event_id=event_id,
            status="failed",
            error="Connection timeout",
        )

        assert isinstance(payload, TaskCallbackPayload)
        assert payload.error == "Connection timeout"


# ============================================================================
# MlInferenceCallbackPayload Tests
# ============================================================================


class TestMlInferenceCallbackPayload:
    """Test ML inference-specific callback payload."""

    def test_ml_payload_success(self):
        """Test ML inference callback with success."""
        event_id = uuid4()
        metadata = {
            "model_id": "model_v2.1",
            "confidence": 0.95,
            "inference_ms": 250,
        }
        payload = MlInferenceCallbackPayload(
            event_id=event_id,
            status="success",
            result={"prediction": "category_a"},
            metadata=metadata,
        )

        assert payload.event_id == event_id
        assert payload.status == "success"
        assert payload.metadata["confidence"] == 0.95

    def test_ml_payload_inherits_task_callback(self):
        """Test that MlInferenceCallbackPayload inherits TaskCallbackPayload."""
        event_id = uuid4()
        payload = MlInferenceCallbackPayload(
            event_id=event_id,
            status="success",
            result={"prediction": "test"},
        )

        assert isinstance(payload, TaskCallbackPayload)


# ============================================================================
# LongRunningTaskProcessor Tests
# ============================================================================


class TestLongRunningTaskProcessor:
    """Test base LongRunningTaskProcessor."""

    @pytest.mark.asyncio
    async def test_processor_publishes_task(self):
        """Test that processor publishes task to broker."""
        broker_mock = AsyncMock()
        processor = LongRunningTaskProcessor(broker_mock, task_subject="test-subject")
        event = Event(
            name="test",
            payload={"param": "value"},
            external_uuid=uuid4(),
        )

        result = await processor.process(event)

        # Verify task published
        broker_mock.publish.assert_called_once()
        call_args = broker_mock.publish.call_args
        assert call_args[1]["stream"] == "test-subject"
        assert call_args[0][0]["event_id"] == str(event.id)
        assert call_args[0][0]["callback_subject"] == f"event-result-{event.id}"

    @pytest.mark.asyncio
    async def test_processor_returns_pending_callback(self):
        """Test that processor returns PENDING_CALLBACK status."""
        broker_mock = AsyncMock()
        processor = LongRunningTaskProcessor(broker_mock, task_subject="test-subject")
        event = Event(
            name="test",
            payload={},
            external_uuid=uuid4(),
        )

        result = await processor.process(event)

        assert result.status == ProcessorResultStatus.PENDING_CALLBACK
        assert result.callback_subject == f"event-result-{event.id}"
        assert result.metadata["task_subject"] == "test-subject"

    def test_processor_no_retry_config(self):
        """Test that long-running processor has no-retry config."""
        broker_mock = AsyncMock()
        processor = LongRunningTaskProcessor(broker_mock, task_subject="test-subject")

        config = processor.get_retry_config()

        assert config.max_attempts == 1
        assert config.initial_backoff == 0.0

    @pytest.mark.asyncio
    async def test_processor_handles_publish_error(self):
        """Test processor raises on publish error."""
        broker_mock = AsyncMock()
        broker_mock.publish.side_effect = RuntimeError("Publish failed")
        processor = LongRunningTaskProcessor(broker_mock, task_subject="test-subject")
        event = Event(
            name="test",
            payload={},
            external_uuid=uuid4(),
        )

        with pytest.raises(RuntimeError):
            await processor.process(event)


# ============================================================================
# Concrete Processor Tests
# ============================================================================


class TestScrapingProcessor:
    """Test ScrapingProcessor implementation."""

    @pytest.mark.asyncio
    async def test_scraping_processor_uses_correct_subject(self):
        """Test that ScrapingProcessor publishes to scraping-task-subject."""
        broker_mock = AsyncMock()
        processor = ScrapingProcessor(broker_mock)
        event = Event(
            name="scraping_task",
            payload={"url": "https://example.com", "selector": ".product"},
            external_uuid=uuid4(),
        )

        result = await processor.process(event)

        broker_mock.publish.assert_called_once()
        call_args = broker_mock.publish.call_args
        assert call_args[1]["stream"] == "scraping-task-subject"
        assert result.metadata["task_subject"] == "scraping-task-subject"


class TestMlInferenceProcessor:
    """Test MlInferenceProcessor implementation."""

    @pytest.mark.asyncio
    async def test_ml_processor_uses_correct_subject(self):
        """Test that MlInferenceProcessor publishes to ml-inference-subject."""
        broker_mock = AsyncMock()
        processor = MlInferenceProcessor(broker_mock)
        event = Event(
            name="ml_inference",
            payload={"model_id": "model_v2", "input": [1, 2, 3]},
            external_uuid=uuid4(),
        )

        result = await processor.process(event)

        broker_mock.publish.assert_called_once()
        call_args = broker_mock.publish.call_args
        assert call_args[1]["stream"] == "ml-inference-subject"
        assert result.metadata["task_subject"] == "ml-inference-subject"


class TestBatchExportProcessor:
    """Test BatchExportProcessor implementation."""

    @pytest.mark.asyncio
    async def test_batch_processor_uses_correct_subject(self):
        """Test that BatchExportProcessor publishes to batch-export-subject."""
        broker_mock = AsyncMock()
        processor = BatchExportProcessor(broker_mock)
        event = Event(
            name="batch_export",
            payload={"query": {}, "format": "csv"},
            external_uuid=uuid4(),
        )

        result = await processor.process(event)

        broker_mock.publish.assert_called_once()
        call_args = broker_mock.publish.call_args
        assert call_args[1]["stream"] == "batch-export-subject"
        assert result.metadata["task_subject"] == "batch-export-subject"


# ============================================================================
# Callback Flow Tests
# ============================================================================


class TestCallbackFlow:
    """Test callback flow for long-running tasks."""

    @pytest.mark.asyncio
    async def test_full_callback_flow(self):
        """Test full callback flow: publish task → receive callback."""
        event_id = uuid4()
        broker_mock = AsyncMock()
        processor = ScrapingProcessor(broker_mock)

        # Step 1: Publish task
        event = Event(
            name="scraping_task",
            payload={"url": "https://example.com"},
            external_uuid=uuid4(),
            id=event_id,
        )
        result = await processor.process(event)

        # Verify task published
        assert result.status == ProcessorResultStatus.PENDING_CALLBACK
        assert result.callback_subject == f"event-result-{event_id}"

        # Step 2: Simulate callback
        callback_payload = TaskCallbackPayload(
            event_id=event_id,
            status="success",
            result={"selectors": 42},
            metadata={"duration_ms": 5000},
        )

        # Verify callback can be created and validated
        assert callback_payload.event_id == event_id
        assert callback_payload.status == "success"
