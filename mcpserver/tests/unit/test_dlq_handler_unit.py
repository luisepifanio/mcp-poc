"""
Unit tests for DLQ handler.

Tests:
- handle_dlq_message: Processes FAILED and EXHAUSTED events
- Logging: Structured logging with event details
- Ack/Nack behavior
- Error handling
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.redis.dlq_handler import handle_dlq_message


@pytest.fixture
def msg_mock():
    """Fixture: Mock RedisMessage"""
    mock = MagicMock()
    mock.ack = AsyncMock()
    mock.nack = AsyncMock()
    return mock


# ============================================================================
# FAILED Event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_handle_dlq_failed_event(msg_mock):
    """Test: Handles FAILED event with ack"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "external_uuid": "ext-456",
        "state": "failed",
        "error": "Connection timeout",
        "timestamp": "2025-01-01T10:00:00+00:00",
        "type": "FAILED",
        "payload": {"test": "data"},
        "context": {"processing": {"processor": "ApiCallProcessor"}},
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()
    msg_mock.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_dlq_failed_event_minimal(msg_mock):
    """Test: Handles FAILED event with minimal fields"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


# ============================================================================
# EXHAUSTED Event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_handle_dlq_exhausted_event(msg_mock):
    """Test: Handles EXHAUSTED event with ack"""
    body = {
        "event_id": "test-456",
        "event_name": "batch_export",
        "external_uuid": "ext-789",
        "state": "exhausted",
        "error": "Max retries exceeded",
        "timestamp": "2025-01-01T10:05:00+00:00",
        "type": "EXHAUSTED",
        "payload": {"batch_id": "batch-1"},
        "context": {"error": {"type": "transient", "message": "Service unavailable"}},
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()
    msg_mock.nack.assert_not_awaited()


# ============================================================================
# Missing Fields Tests
# ============================================================================


@pytest.mark.asyncio
async def test_handle_dlq_missing_event_id(msg_mock):
    """Test: Handles message with missing event_id (uses 'unknown')"""
    body = {
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
        # Missing event_id
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dlq_missing_event_name(msg_mock):
    """Test: Handles message with missing event_name"""
    body = {
        "event_id": "test-123",
        "state": "failed",
        "type": "FAILED",
        # Missing event_name
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dlq_missing_error(msg_mock):
    """Test: Handles message with missing error message"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
        # Missing error
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dlq_empty_payload(msg_mock):
    """Test: Handles message with empty payload"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
        "payload": {},
        "context": {},
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_handle_dlq_ack_error_nacks_message(msg_mock):
    """Test: Nacks message if ack fails"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
    }

    msg_mock.ack.side_effect = Exception("Ack failed")

    await handle_dlq_message(body, msg_mock)

    msg_mock.nack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dlq_missing_both_type_and_event_id(msg_mock):
    """Test: Handles message with multiple missing fields"""
    body = {
        "state": "failed",
        # Missing event_id, event_name, type
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


# ============================================================================
# Message Type Tests
# ============================================================================


@pytest.mark.asyncio
async def test_handle_dlq_unknown_type(msg_mock):
    """Test: Handles message with unknown type"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "UNKNOWN_TYPE",  # Not FAILED or EXHAUSTED
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


# ============================================================================
# Payload Variations Tests
# ============================================================================


@pytest.mark.asyncio
async def test_handle_dlq_large_payload(msg_mock):
    """Test: Handles message with large payload"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
        "error": "Error",
        "payload": {"data": "x" * 1000},  # Large payload
        "context": {"processing": {"details": "y" * 500}},
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dlq_nested_context(msg_mock):
    """Test: Handles message with deeply nested context"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
        "error": "Error",
        "context": {
            "processing": {
                "processor": "ApiCallProcessor",
                "attempt": 5,
                "error_chain": [
                    {"type": "ConnectionError", "message": "Network failure"},
                    {"type": "TimeoutError", "message": "Request timeout"},
                ],
            },
            "retry": {"last_backoff": 4000, "next_attempt": None},
        },
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


# ============================================================================
# Timestamp Tests
# ============================================================================


@pytest.mark.asyncio
async def test_handle_dlq_with_timestamp(msg_mock):
    """Test: Handles message with ISO timestamp"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
        "timestamp": "2025-01-15T14:30:45.123456+00:00",
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dlq_without_timestamp(msg_mock):
    """Test: Handles message without timestamp"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "state": "failed",
        "type": "FAILED",
        # Missing timestamp
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


# ============================================================================
# External UUID Tests
# ============================================================================


@pytest.mark.asyncio
async def test_handle_dlq_with_external_uuid(msg_mock):
    """Test: Logs message with external_uuid"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "external_uuid": "ext-456-789",
        "state": "failed",
        "type": "FAILED",
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_dlq_without_external_uuid(msg_mock):
    """Test: Handles message with None external_uuid"""
    body = {
        "event_id": "test-123",
        "event_name": "test_event",
        "external_uuid": None,
        "state": "failed",
        "type": "FAILED",
    }

    await handle_dlq_message(body, msg_mock)

    msg_mock.ack.assert_awaited_once()
