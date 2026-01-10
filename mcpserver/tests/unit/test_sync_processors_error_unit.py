"""
Unit tests for sync_processors error scenarios.

Tests error classification, retry behavior, and edge cases for:
- ApiCallProcessor: HTTP errors (4xx, 5xx, timeouts)
- GrpcProcessor: gRPC status codes
- LocalUseCaseProcessor: Local errors
- Retry exhaustion scenarios
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from result import Err, Ok

from app.core.entities import Event, EventState
from app.core.processors import ErrorType, ProcessorResultStatus
from app.infrastructure.processors.sync_processors import ApiCallProcessor

# ===== ApiCallProcessor Error Tests =====


@pytest.mark.asyncio
async def test_api_processor_http_400_permanent_error():
    """
    HTTP 4xx errors should be classified as PERMANENT (no retries).

    ✅ FIXED: AsyncRetrying now uses retry_if_not_exception_type(ValueError)
    to prevent retrying PERMANENT errors (ValueError from 4xx HTTP responses).
    """
    processor = ApiCallProcessor(timeout=5.0)

    event = Event(
        id=uuid4(),
        name="test_api_call",
        state=EventState.PENDING,
        payload={
            "method": "POST",
            "url": "https://api.example.com/endpoint",
            "body": {"test": "data"},
        },
    )

    # Mock HTTP client to return 400 Bad Request
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Should raise ValueError (converted from 4xx)
        with pytest.raises(ValueError, match="HTTP 400"):
            await processor.process(event)

        # ✅ FIXED: Should only attempt once (no retries for PERMANENT errors)
        assert mock_client.request.call_count == 1


@pytest.mark.asyncio
async def test_api_processor_http_503_transient_retries():
    """HTTP 5xx errors should retry (TRANSIENT)."""
    processor = ApiCallProcessor(timeout=5.0)

    event = Event(
        id=uuid4(),
        name="test_api_call",
        state=EventState.PENDING,
        payload={
            "method": "GET",
            "url": "https://api.example.com/resource",
        },
    )

    # Mock HTTP client: 2 failures (503), then success (200)
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()

        # Response 1: 503 Service Unavailable
        mock_response_503 = MagicMock()
        mock_response_503.status_code = 503
        mock_response_503.text = "Service Unavailable"
        mock_response_503.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=mock_response_503,
        )

        # Response 2: 200 OK
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = '{"result": "success"}'
        mock_response_200.json.return_value = {"result": "success"}
        mock_response_200.headers = {"content-type": "application/json"}
        mock_response_200.raise_for_status.return_value = None

        # Side effect: fail twice, succeed on third attempt
        mock_client.request = AsyncMock(
            side_effect=[mock_response_503, mock_response_503, mock_response_200]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Should succeed after retries
        result = await processor.process(event)

        assert result.status == ProcessorResultStatus.SUCCESS
        assert result.data["status_code"] == 200
        assert result.data["body"] == {"result": "success"}

        # Should have attempted 3 times (1 initial + 2 retries)
        assert mock_client.request.call_count == 3


@pytest.mark.asyncio
async def test_api_processor_timeout_transient():
    """Timeout errors should be classified as TRANSIENT (retryable)."""
    processor = ApiCallProcessor(timeout=1.0)

    event = Event(
        id=uuid4(),
        name="test_api_call",
        state=EventState.PENDING,
        payload={
            "method": "GET",
            "url": "https://slow-api.example.com/timeout",
            "timeout": 0.5,  # Very short timeout
        },
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()

        # Simulate timeout
        mock_client.request = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Should raise TimeoutException after all retries
        with pytest.raises(httpx.TimeoutException):
            await processor.process(event)

        # Should attempt multiple times (max_attempts = 5)
        assert mock_client.request.call_count == 5


@pytest.mark.asyncio
async def test_api_processor_invalid_method_validation():
    """Invalid HTTP method should raise ValueError immediately."""
    processor = ApiCallProcessor()

    event = Event(
        id=uuid4(),
        name="test_api_call",
        state=EventState.PENDING,
        payload={
            "method": "INVALID",
            "url": "https://api.example.com/endpoint",
        },
    )

    # Should fail validation without making HTTP request
    with pytest.raises(ValueError, match="Invalid HTTP method"):
        await processor.process(event)


@pytest.mark.asyncio
async def test_api_processor_missing_url_validation():
    """Missing URL should raise ValueError immediately."""
    processor = ApiCallProcessor()

    event = Event(
        id=uuid4(),
        name="test_api_call",
        state=EventState.PENDING,
        payload={
            "method": "GET",
            # No URL
        },
    )

    # Should fail validation
    with pytest.raises(ValueError, match="url"):
        await processor.process(event)


@pytest.mark.asyncio
async def test_api_processor_classify_error_permanent():
    """Test error classification for PERMANENT errors."""
    processor = ApiCallProcessor()

    # ValueError (from 4xx) should be PERMANENT
    exc = ValueError("HTTP 404: Not Found")
    assert processor.classify_error(exc) == ErrorType.PERMANENT

    # TypeError should be PERMANENT
    exc = TypeError("Invalid type")
    assert processor.classify_error(exc) == ErrorType.PERMANENT


@pytest.mark.asyncio
async def test_api_processor_classify_error_transient():
    """Test error classification for TRANSIENT errors."""
    processor = ApiCallProcessor()

    # HTTPStatusError (5xx) should be TRANSIENT
    mock_response = MagicMock()
    mock_response.status_code = 503
    exc = httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=MagicMock(),
        response=mock_response,
    )
    assert processor.classify_error(exc) == ErrorType.TRANSIENT

    # TimeoutException should be TRANSIENT
    exc = httpx.TimeoutException("Request timed out")
    assert processor.classify_error(exc) == ErrorType.TRANSIENT

    # ConnectError should be TRANSIENT
    exc = httpx.ConnectError("Connection failed")
    assert processor.classify_error(exc) == ErrorType.TRANSIENT


@pytest.mark.asyncio
async def test_api_processor_retry_config():
    """Test retry configuration returns expected values."""
    processor = ApiCallProcessor()

    config = processor.get_retry_config()

    # Verify retry configuration
    assert config.max_attempts == 5
    assert config.initial_backoff == 0.5  # 500ms
    assert config.max_backoff == 2.0  # 2s
    assert config.backoff_multiplier == 2.0
    assert config.fast_retry_count == 2
    assert config.fast_retry_delay == 0.1  # 100ms


@pytest.mark.asyncio
async def test_api_processor_retry_exhaustion():
    """Test behavior when all retries are exhausted."""
    processor = ApiCallProcessor(timeout=1.0)

    event = Event(
        id=uuid4(),
        name="test_api_call",
        state=EventState.PENDING,
        payload={
            "method": "GET",
            "url": "https://api.example.com/always-fails",
        },
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()

        # Always fail with 503
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Always fails"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        # Should raise HTTPStatusError after all retries exhausted
        with pytest.raises(httpx.HTTPStatusError):
            await processor.process(event)

        # Should have attempted max_attempts times
        assert mock_client.request.call_count == 5


# ===== Additional Coverage Tests =====


@pytest.mark.asyncio
async def test_api_processor_success_with_empty_response():
    """Test successful API call with empty response body."""
    processor = ApiCallProcessor()

    event = Event(
        id=uuid4(),
        name="test_api_call",
        state=EventState.PENDING,
        payload={
            "method": "DELETE",
            "url": "https://api.example.com/resource/123",
        },
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()

        # Response with no body
        mock_response = MagicMock()
        mock_response.status_code = 204  # No Content
        mock_response.text = ""
        mock_response.json.return_value = None
        mock_response.headers = {}
        mock_response.raise_for_status.return_value = None

        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await processor.process(event)

        assert result.status == ProcessorResultStatus.SUCCESS
        assert result.data["status_code"] == 204
        assert result.data["body"] is None


@pytest.mark.asyncio
async def test_api_processor_custom_headers():
    """Test API call with custom headers."""
    processor = ApiCallProcessor()

    event = Event(
        id=uuid4(),
        name="test_api_call",
        state=EventState.PENDING,
        payload={
            "method": "POST",
            "url": "https://api.example.com/endpoint",
            "headers": {
                "Authorization": "Bearer token123",
                "Content-Type": "application/json",
            },
            "body": {"test": "data"},
        },
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_response.json.return_value = {"success": True}
        mock_response.headers = {}
        mock_response.raise_for_status.return_value = None

        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client

        result = await processor.process(event)

        assert result.status == ProcessorResultStatus.SUCCESS

        # Verify headers were passed correctly
        call_args = mock_client.request.call_args
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer token123"
        assert call_args.kwargs["headers"]["Content-Type"] == "application/json"
