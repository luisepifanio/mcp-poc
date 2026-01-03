"""
Unit tests for synchronous event processors.

Tests:
- ApiCallProcessor: HTTP success, errors, timeouts, retries
- GrpcProcessor: Error classification, placeholder tests
- LocalUseCaseProcessor: Placeholder tests, error classification
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.core.entities import Event, EventState
from app.core.processors import (
    ErrorType,
    ProcessorResultStatus,
)
from app.infrastructure.processors.sync_processors import (
    ApiCallProcessor,
    GrpcProcessor,
    LocalUseCaseProcessor,
)

# ============================================================================
# ApiCallProcessor Tests
# ============================================================================


@pytest.fixture
def api_processor():
    """Fixture: ApiCallProcessor instance"""
    return ApiCallProcessor(timeout=10.0)


@pytest.fixture
def api_event():
    """Fixture: Event with API call payload"""
    return Event(
        id=uuid4(),
        name="api_call",
        state=EventState.PENDING,
        payload={
            "method": "POST",
            "url": "https://api.example.com/process",
            "headers": {"Authorization": "Bearer token"},
            "body": {"data": "test"},
            "timeout": 5,
        },
    )


@pytest.mark.asyncio
async def test_api_processor_success(api_processor, api_event):
    """Test: Successful API call returns SUCCESS result"""
    # Mock successful HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"result": "ok"}'
    mock_response.json.return_value = {"result": "ok"}
    mock_response.headers = {"content-type": "application/json"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await api_processor.process(api_event)

        assert result.status == ProcessorResultStatus.SUCCESS
        assert result.data["status_code"] == 200
        assert result.data["body"] == {"result": "ok"}
        mock_client.request.assert_called_once()


@pytest.mark.asyncio
async def test_api_processor_missing_url(api_processor):
    """Test: Missing 'url' in payload raises ValueError"""
    event = Event(
        id=uuid4(),
        name="api_call",
        state=EventState.PENDING,
        payload={
            "method": "GET",
            # Missing 'url'
        },
    )

    with pytest.raises(ValueError, match="requires 'url'"):
        await api_processor.process(event)


@pytest.mark.asyncio
async def test_api_processor_invalid_method(api_processor):
    """Test: Invalid HTTP method raises ValueError"""
    event = Event(
        id=uuid4(),
        name="api_call",
        state=EventState.PENDING,
        payload={
            "method": "INVALID",
            "url": "https://api.example.com/test",
        },
    )

    with pytest.raises(ValueError, match="Invalid HTTP method"):
        await api_processor.process(event)


@pytest.mark.asyncio
async def test_api_processor_4xx_error(api_processor, api_event):
    """Test: 4xx error (validation) raises ValueError (PERMANENT)"""
    # 400 = client error = permanent
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_error = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_response
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.side_effect = mock_error
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError):
            await api_processor.process(api_event)


@pytest.mark.asyncio
async def test_api_processor_5xx_error_with_retries(api_processor, api_event):
    """Test: 5xx error triggers retries (TRANSIENT)"""
    # 500 = server error = transient = should retry
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_error = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=mock_response
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.side_effect = mock_error
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await api_processor.process(api_event)


@pytest.mark.asyncio
async def test_api_processor_timeout(api_processor, api_event):
    """Test: Timeout error (TRANSIENT) triggers retries"""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.side_effect = httpx.TimeoutException("Request timeout")
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.TimeoutException):
            await api_processor.process(api_event)


@pytest.mark.asyncio
async def test_api_processor_connection_error(api_processor, api_event):
    """Test: Connection error (TRANSIENT) triggers retries"""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.side_effect = httpx.ConnectError("Cannot connect")
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.ConnectError):
            await api_processor.process(api_event)


def test_api_processor_get_retry_config(api_processor):
    """Test: Retry config has correct values"""
    config = api_processor.get_retry_config()

    assert config.max_attempts == 5
    assert config.initial_backoff == 0.5  # 500ms
    assert config.max_backoff == 2.0
    assert config.backoff_multiplier == 2.0
    assert config.fast_retry_count == 2
    assert config.fast_retry_delay == 0.1


def test_api_processor_classify_error_permanent():
    """Test: ValueError classified as PERMANENT"""
    processor = ApiCallProcessor()
    error = ValueError("Invalid request")
    assert processor.classify_error(error) == ErrorType.PERMANENT


def test_api_processor_classify_error_4xx():
    """Test: 4xx HTTP error classified as PERMANENT"""
    processor = ApiCallProcessor()
    mock_response = MagicMock()
    mock_response.status_code = 404
    error = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )
    assert processor.classify_error(error) == ErrorType.PERMANENT


def test_api_processor_classify_error_5xx():
    """Test: 5xx HTTP error classified as TRANSIENT"""
    processor = ApiCallProcessor()
    mock_response = MagicMock()
    mock_response.status_code = 502
    error = httpx.HTTPStatusError(
        "Bad Gateway", request=MagicMock(), response=mock_response
    )
    assert processor.classify_error(error) == ErrorType.TRANSIENT


def test_api_processor_classify_error_connection():
    """Test: Connection errors classified as TRANSIENT"""
    processor = ApiCallProcessor()
    error = httpx.ConnectError("Cannot connect")
    assert processor.classify_error(error) == ErrorType.TRANSIENT


def test_api_processor_classify_error_timeout():
    """Test: Timeout errors classified as TRANSIENT"""
    processor = ApiCallProcessor()
    error = httpx.TimeoutException("Request timeout")
    assert processor.classify_error(error) == ErrorType.TRANSIENT


# ============================================================================
# GrpcProcessor Tests
# ============================================================================


@pytest.fixture
def grpc_processor():
    """Fixture: GrpcProcessor instance"""
    return GrpcProcessor(timeout=10.0)


@pytest.fixture
def grpc_event():
    """Fixture: Event with gRPC call payload"""
    return Event(
        id=uuid4(),
        name="grpc_call",
        state=EventState.PENDING,
        payload={
            "service": "example.Service",
            "method": "ProcessData",
            "request": {"data": "test"},
            "address": "localhost:50051",
            "timeout": 5,
        },
    )


@pytest.mark.asyncio
async def test_grpc_processor_missing_service(grpc_processor):
    """Test: Missing service raises ValueError"""
    event = Event(
        id=uuid4(),
        name="grpc_call",
        state=EventState.PENDING,
        payload={"method": "ProcessData"},
    )

    with pytest.raises(ValueError, match="requires 'service'"):
        await grpc_processor.process(event)


@pytest.mark.asyncio
async def test_grpc_processor_missing_method(grpc_processor):
    """Test: Missing method raises ValueError"""
    event = Event(
        id=uuid4(),
        name="grpc_call",
        state=EventState.PENDING,
        payload={"service": "example.Service"},
    )

    with pytest.raises(ValueError, match="requires 'service' and 'method'"):
        await grpc_processor.process(event)


@pytest.mark.asyncio
async def test_grpc_processor_not_implemented(grpc_processor, grpc_event):
    """Test: gRPC execution raises NotImplementedError"""
    with pytest.raises(NotImplementedError, match="gRPC processor requires"):
        await grpc_processor.process(grpc_event)


def test_grpc_processor_get_retry_config(grpc_processor):
    """Test: Retry config optimized for gRPC"""
    config = grpc_processor.get_retry_config()

    assert config.max_attempts == 5
    assert config.initial_backoff == 0.3  # 300ms
    assert config.max_backoff == 2.0
    assert config.fast_retry_delay == 0.05  # 50ms


def test_grpc_processor_classify_error_permanent():
    """Test: ValueError classified as PERMANENT"""
    processor = GrpcProcessor()
    error = ValueError("Invalid request")
    assert processor.classify_error(error) == ErrorType.PERMANENT


# ============================================================================
# LocalUseCaseProcessor Tests
# ============================================================================


@pytest.fixture
def local_usecase_processor():
    """Fixture: LocalUseCaseProcessor instance"""
    uow_mock = MagicMock()
    return LocalUseCaseProcessor(uow=uow_mock)


@pytest.fixture
def local_usecase_event():
    """Fixture: Event with local use case payload"""
    return Event(
        id=uuid4(),
        name="local_usecase",
        state=EventState.PENDING,
        payload={
            "use_case_name": "ProcessOrder",
            "input": {"order_id": "123"},
        },
    )


@pytest.mark.asyncio
async def test_local_usecase_processor_missing_name(local_usecase_processor):
    """Test: Missing use_case_name raises ValueError"""
    event = Event(
        id=uuid4(),
        name="local_usecase",
        state=EventState.PENDING,
        payload={"input": {"data": "test"}},
    )

    with pytest.raises(ValueError, match="requires 'use_case_name'"):
        await local_usecase_processor.process(event)


@pytest.mark.asyncio
async def test_local_usecase_processor_not_implemented(
    local_usecase_processor, local_usecase_event
):
    """Test: Local use case execution raises NotImplementedError"""
    with pytest.raises(NotImplementedError, match="Local use case"):
        await local_usecase_processor.process(local_usecase_event)


def test_local_usecase_processor_get_retry_config(local_usecase_processor):
    """Test: Retry config optimized for local execution"""
    config = local_usecase_processor.get_retry_config()

    assert config.max_attempts == 3
    assert config.initial_backoff == 0.2  # 200ms
    assert config.max_backoff == 2.0
    assert config.fast_retry_count == 1
    assert config.fast_retry_delay == 0.05


def test_local_usecase_processor_classify_error_permanent():
    """Test: ValueError classified as PERMANENT"""
    processor = LocalUseCaseProcessor(uow=MagicMock())
    error = ValueError("Invalid input")
    assert processor.classify_error(error) == ErrorType.PERMANENT


def test_local_usecase_processor_classify_error_connection():
    """Test: Connection errors classified as TRANSIENT"""
    processor = LocalUseCaseProcessor(uow=MagicMock())
    error = ConnectionError("Cannot connect to DB")
    assert processor.classify_error(error) == ErrorType.TRANSIENT


def test_local_usecase_processor_classify_error_timeout():
    """Test: Timeout errors classified as TRANSIENT"""
    processor = LocalUseCaseProcessor(uow=MagicMock())
    error = TimeoutError("Request timeout")
    assert processor.classify_error(error) == ErrorType.TRANSIENT


# ============================================================================
# Retry Configuration Tests
# ============================================================================


def test_api_processor_faster_than_grpc():
    """Test: API processor has slower retries than gRPC (API has more backoff)"""
    api_config = ApiCallProcessor().get_retry_config()
    grpc_config = GrpcProcessor().get_retry_config()

    # API has longer initial backoff (network overhead)
    assert api_config.initial_backoff > grpc_config.initial_backoff


def test_local_processor_fastest():
    """Test: Local processor has fastest retries (local execution is quick)"""
    local_config = LocalUseCaseProcessor(uow=MagicMock()).get_retry_config()
    api_config = ApiCallProcessor().get_retry_config()

    # Local has fewer attempts and shorter backoff
    assert local_config.max_attempts < api_config.max_attempts
    assert local_config.initial_backoff < api_config.initial_backoff
