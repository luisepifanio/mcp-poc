"""
Unit tests for message publisher implementation.

Tests:
- RedisMessagePublisher: publish_failed_event, publish_exhausted_event, publish_success_event
- Error handling when broker fails
- Proper formatting of published messages
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.entities import Event, EventState
from app.infrastructure.publishers.redis_message_publisher import (
    RedisMessagePublisher,
)


@pytest.fixture
def broker_mock():
    """Fixture: Mock RedisBroker"""
    mock = MagicMock()
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def publisher(broker_mock):
    """Fixture: RedisMessagePublisher instance"""
    return RedisMessagePublisher(broker_mock, dlq_stream="test-dlq")


@pytest.fixture
def test_event():
    """Fixture: Test event"""
    return Event(
        id=uuid4(),
        name="test_event",
        state=EventState.FAILED,
        payload={"test": "data"},
        external_uuid=uuid4(),
        context={"processing": {"processor": "TestProcessor"}},
    )


# ============================================================================
# publish_failed_event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_publish_failed_event(publisher, broker_mock, test_event):
    """Test: Publishes FAILED event with correct structure"""
    error = "Connection timeout"

    await publisher.publish_failed_event(test_event, error)

    broker_mock.publish.assert_awaited_once()
    call_args = broker_mock.publish.call_args

    message = call_args[0][0]
    assert message["event_id"] == str(test_event.id)
    assert message["event_name"] == "test_event"
    assert message["state"] == "failed"
    assert message["error"] == error
    assert message["type"] == "FAILED"
    assert call_args[1]["stream"] == "test-dlq"


@pytest.mark.asyncio
async def test_publish_failed_event_includes_payload(publisher, broker_mock, test_event):
    """Test: Published message includes payload and context"""
    await publisher.publish_failed_event(test_event, "Error")

    message = broker_mock.publish.call_args[0][0]
    assert message["payload"] == test_event.payload
    assert message["context"] == test_event.context


@pytest.mark.asyncio
async def test_publish_failed_event_includes_external_uuid(
    publisher, broker_mock, test_event
):
    """Test: Published message includes external_uuid"""
    await publisher.publish_failed_event(test_event, "Error")

    message = broker_mock.publish.call_args[0][0]
    assert message["external_uuid"] == str(test_event.external_uuid)


@pytest.mark.asyncio
async def test_publish_failed_event_handles_missing_external_uuid(publisher, broker_mock):
    """Test: Handles event without external_uuid"""
    event = Event(
        id=uuid4(),
        name="test_event",
        state=EventState.FAILED,
        payload={},
        external_uuid=None,
    )

    await publisher.publish_failed_event(event, "Error")

    message = broker_mock.publish.call_args[0][0]
    assert message["external_uuid"] is None


@pytest.mark.asyncio
async def test_publish_failed_event_broker_error(publisher, broker_mock, test_event):
    """Test: Raises exception when broker fails"""
    broker_mock.publish.side_effect = Exception("Broker connection failed")

    with pytest.raises(Exception, match="Broker connection failed"):
        await publisher.publish_failed_event(test_event, "Error")


# ============================================================================
# publish_exhausted_event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_publish_exhausted_event(publisher, broker_mock):
    """Test: Publishes EXHAUSTED event with correct structure"""
    event = Event(
        id=uuid4(),
        name="test_event",
        state=EventState.EXHAUSTED,
        payload={},
        external_uuid=uuid4(),
    )
    error = "Max retries exceeded"

    await publisher.publish_exhausted_event(event, error)

    broker_mock.publish.assert_awaited_once()
    message = broker_mock.publish.call_args[0][0]

    assert message["event_id"] == str(event.id)
    assert message["state"] == "exhausted"
    assert message["error"] == error
    assert message["type"] == "EXHAUSTED"


@pytest.mark.asyncio
async def test_publish_exhausted_event_broker_error(publisher, broker_mock):
    """Test: Raises exception when broker fails"""
    event = Event(
        id=uuid4(),
        name="test_event",
        state=EventState.EXHAUSTED,
        payload={},
    )
    broker_mock.publish.side_effect = Exception("Broker error")

    with pytest.raises(Exception, match="Broker error"):
        await publisher.publish_exhausted_event(event, "Error")


# ============================================================================
# publish_success_event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_publish_success_event_no_broker_call(publisher, broker_mock):
    """Test: Success event doesn't publish to broker (logging only)"""
    event = Event(
        id=uuid4(),
        name="test_event",
        state=EventState.COMPLETED,
        payload={},
    )

    await publisher.publish_success_event(event, {"result": "success"})

    # Success events are logged, not published to DLQ
    broker_mock.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_success_event_with_result(publisher, broker_mock):
    """Test: Success event accepts result data"""
    event = Event(
        id=uuid4(),
        name="test_event",
        state=EventState.COMPLETED,
        payload={},
    )
    result = {"processed": 100, "items": [1, 2, 3]}

    # Should not raise
    await publisher.publish_success_event(event, result)

    broker_mock.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_success_event_without_result(publisher, broker_mock):
    """Test: Success event works without result data"""
    event = Event(
        id=uuid4(),
        name="test_event",
        state=EventState.COMPLETED,
        payload={},
    )

    # Should not raise
    await publisher.publish_success_event(event)

    broker_mock.publish.assert_not_awaited()


# ============================================================================
# Message Timestamp Tests
# ============================================================================


@pytest.mark.asyncio
async def test_published_message_has_timestamp(publisher, broker_mock, test_event):
    """Test: Published messages include timestamp"""
    await publisher.publish_failed_event(test_event, "Error")

    message = broker_mock.publish.call_args[0][0]
    assert "timestamp" in message
    # Timestamp should be ISO format
    assert "T" in message["timestamp"]  # ISO format has T separator


# ============================================================================
# Stream Configuration Tests
# ============================================================================


def test_publisher_custom_dlq_stream():
    """Test: Publisher respects custom DLQ stream name"""
    broker_mock = MagicMock()
    broker_mock.publish = AsyncMock()

    publisher = RedisMessagePublisher(broker_mock, dlq_stream="custom-dlq-stream")

    assert publisher.dlq_stream == "custom-dlq-stream"


def test_publisher_default_dlq_stream():
    """Test: Publisher uses default DLQ stream name"""
    broker_mock = MagicMock()
    broker_mock.publish = AsyncMock()

    publisher = RedisMessagePublisher(broker_mock)

    assert publisher.dlq_stream == "dlq-subject"


# ============================================================================
# Error Message Formats
# ============================================================================


@pytest.mark.asyncio
async def test_publish_failed_event_various_errors(publisher, broker_mock, test_event):
    """Test: Publisher handles various error message formats"""
    errors = [
        "Simple error",
        "Error with numbers: 404, 500",
        "Error with special chars: !@#$%^&*()",
        "Very long error message: " + "x" * 100,
    ]

    for error in errors:
        broker_mock.reset_mock()
        await publisher.publish_failed_event(test_event, error)

        message = broker_mock.publish.call_args[0][0]
        assert message["error"] == error
