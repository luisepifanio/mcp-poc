"""Unit tests for RedisPublisher implementation."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from app.core.publisher import ErrorDetail
from app.infrastructure.publishers import RedisPublisher


class SampleMessage(BaseModel):
    """Sample Pydantic model for testing."""

    text: str
    count: int


@pytest.fixture
def mock_broker() -> MagicMock:
    """Create a mock RedisBroker."""
    broker = MagicMock()
    broker.publish = AsyncMock()
    return broker


@pytest.fixture
def publisher(mock_broker: MagicMock) -> RedisPublisher:
    """Create a RedisPublisher with mocked broker."""
    return RedisPublisher(mock_broker)


class TestRedisPublisherPublish:
    """Unit tests for RedisPublisher.publish method."""

    @pytest.mark.asyncio
    async def test_publish_dict_message_returns_ok(
        self, publisher: RedisPublisher, mock_broker: MagicMock
    ) -> None:
        """Test publishing a dict message returns Ok(None)."""
        message = {"hello": "world", "count": 42}
        stream = "test-stream"

        result = await publisher.publish(message, stream)

        assert result.is_ok()
        assert result.unwrap() is None
        mock_broker.publish.assert_called_once_with(message, stream=stream)

    @pytest.mark.asyncio
    async def test_publish_basemodel_message_returns_ok(
        self, publisher: RedisPublisher, mock_broker: MagicMock
    ) -> None:
        """Test publishing a Pydantic BaseModel message returns Ok(None)."""
        message = SampleMessage(text="hello", count=5)
        stream = "test-stream"

        result = await publisher.publish(message, stream)

        assert result.is_ok()
        mock_broker.publish.assert_called_once_with(
            {"text": "hello", "count": 5}, stream=stream
        )

    @pytest.mark.asyncio
    async def test_publish_scalar_values(
        self, publisher: RedisPublisher, mock_broker: MagicMock
    ) -> None:
        """Test publishing scalar JSON values."""
        for value in ["string", 42, 3.14, True, None]:
            mock_broker.publish.reset_mock()

            result = await publisher.publish(value, "test-stream")

            assert result.is_ok()
            mock_broker.publish.assert_called_once_with(value, stream="test-stream")

    @pytest.mark.asyncio
    async def test_publish_list_message_returns_ok(
        self, publisher: RedisPublisher, mock_broker: MagicMock
    ) -> None:
        """Test publishing a list message returns Ok(None)."""
        message = ["item1", "item2", 123]
        stream = "test-stream"

        result = await publisher.publish(message, stream)

        assert result.is_ok()
        mock_broker.publish.assert_called_once_with(message, stream=stream)

    @pytest.mark.asyncio
    async def test_publish_broker_exception_returns_err(
        self, publisher: RedisPublisher, mock_broker: MagicMock
    ) -> None:
        """Test that broker exceptions return Err(ErrorDetail)."""
        mock_broker.publish.side_effect = Exception("Connection failed")

        result = await publisher.publish({"test": "data"}, "test-stream")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ErrorDetail)
        assert error.error == "PUBLISH_FAILED"
        assert "Connection failed" in error.detail

    @pytest.mark.asyncio
    async def test_publish_preserves_stream_name(
        self, publisher: RedisPublisher, mock_broker: MagicMock
    ) -> None:
        """Test that stream name is correctly passed to broker."""
        streams = ["demo-subject", "events-topic", "custom-stream"]

        for stream in streams:
            mock_broker.publish.reset_mock()

            await publisher.publish({"msg": "test"}, stream)

            mock_broker.publish.assert_called_once()
            call_args = mock_broker.publish.call_args
            assert call_args.kwargs["stream"] == stream

    @pytest.mark.asyncio
    async def test_publish_converts_basemodel_to_dict(
        self, publisher: RedisPublisher, mock_broker: MagicMock
    ) -> None:
        """Test that BaseModel is converted to dict before publishing."""
        message = SampleMessage(text="test", count=10)

        await publisher.publish(message, "stream")

        # Verify that the dict version was sent, not the BaseModel
        call_args = mock_broker.publish.call_args
        published_data = call_args[0][0]  # First positional argument
        assert isinstance(published_data, dict)
        assert published_data == {"text": "test", "count": 10}

    @pytest.mark.asyncio
    async def test_publish_timeout_error_returns_err(
        self, publisher: RedisPublisher, mock_broker: MagicMock
    ) -> None:
        """Test that timeout errors are caught and return Err."""
        mock_broker.publish.side_effect = TimeoutError("Broker timeout")

        result = await publisher.publish({"data": "test"}, "stream")

        assert result.is_err()
        error = result.unwrap_err()
        assert "Broker timeout" in error.detail
