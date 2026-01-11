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
from tests.unit.conftest import FAST_TEST_RETRY_CONFIG

# ============================================================================
# ApiCallProcessor Tests
# ============================================================================


@pytest.fixture
def api_processor() -> ApiCallProcessor:
    """Fixture: ApiCallProcessor instance with fast retry config"""
    return ApiCallProcessor(timeout=10.0, retry_config=FAST_TEST_RETRY_CONFIG)


@pytest.fixture
def api_event() -> Event:
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
async def test_api_processor_success(
    api_processor: ApiCallProcessor, api_event: Event
) -> None:
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
async def test_api_processor_missing_url(api_processor: ApiCallProcessor) -> None:
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

    with pytest.raises(ValueError, match="INVALID_HTTP_URL"):
        await api_processor.process(event)


@pytest.mark.asyncio
async def test_api_processor_invalid_method(api_processor: ApiCallProcessor) -> None:
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

    with pytest.raises(ValueError, match="INVALID_HTTP_METHOD"):
        await api_processor.process(event)


@pytest.mark.asyncio
async def test_api_processor_4xx_error(
    api_processor: ApiCallProcessor, api_event: Event
) -> None:
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
async def test_api_processor_5xx_error_with_retries(
    api_processor: ApiCallProcessor, api_event: Event
) -> None:
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
async def test_api_processor_timeout(
    api_processor: ApiCallProcessor, api_event: Event
) -> None:
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
async def test_api_processor_connection_error(
    api_processor: ApiCallProcessor, api_event: Event
) -> None:
    """Test: Connection error (TRANSIENT) triggers retries"""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.request.side_effect = httpx.ConnectError("Cannot connect")
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.ConnectError):
            await api_processor.process(api_event)


def test_api_processor_get_retry_config(api_processor: ApiCallProcessor) -> None:
    """Test: Retry config has correct values"""
    config = api_processor.get_retry_config()

    assert config.max_attempts == FAST_TEST_RETRY_CONFIG.max_attempts
    assert config.initial_backoff == FAST_TEST_RETRY_CONFIG.initial_backoff
    assert config.max_backoff == FAST_TEST_RETRY_CONFIG.max_backoff
    assert config.backoff_multiplier == FAST_TEST_RETRY_CONFIG.backoff_multiplier
    assert config.fast_retry_count == FAST_TEST_RETRY_CONFIG.fast_retry_count
    assert config.fast_retry_delay == FAST_TEST_RETRY_CONFIG.fast_retry_delay


def test_api_processor_classify_error_permanent() -> None:
    """Test: ValueError classified as PERMANENT"""
    processor = ApiCallProcessor(retry_config=FAST_TEST_RETRY_CONFIG)
    error = ValueError("Invalid request")
    assert processor.classify_error(error) == ErrorType.PERMANENT


def test_api_processor_classify_error_4xx() -> None:
    """Test: 4xx HTTP error classified as PERMANENT"""
    processor = ApiCallProcessor(retry_config=FAST_TEST_RETRY_CONFIG)
    mock_response = MagicMock()
    mock_response.status_code = 404
    error = httpx.HTTPStatusError(
        "Not Found", request=MagicMock(), response=mock_response
    )
    assert processor.classify_error(error) == ErrorType.PERMANENT


def test_api_processor_classify_error_5xx() -> None:
    """Test: 5xx HTTP error classified as TRANSIENT"""
    processor = ApiCallProcessor(retry_config=FAST_TEST_RETRY_CONFIG)
    mock_response = MagicMock()
    mock_response.status_code = 502
    error = httpx.HTTPStatusError(
        "Bad Gateway", request=MagicMock(), response=mock_response
    )
    assert processor.classify_error(error) == ErrorType.TRANSIENT


def test_api_processor_classify_error_connection() -> None:
    """Test: Connection errors classified as TRANSIENT"""
    processor = ApiCallProcessor(retry_config=FAST_TEST_RETRY_CONFIG)
    error = httpx.ConnectError("Cannot connect")
    assert processor.classify_error(error) == ErrorType.TRANSIENT


def test_api_processor_classify_error_timeout() -> None:
    """Test: Timeout errors classified as TRANSIENT"""
    processor = ApiCallProcessor(retry_config=FAST_TEST_RETRY_CONFIG)
    error = httpx.TimeoutException("Request timeout")
    assert processor.classify_error(error) == ErrorType.TRANSIENT


# ============================================================================
# GrpcProcessor Tests
# ============================================================================


@pytest.fixture
def grpc_processor() -> GrpcProcessor:
    """Fixture: GrpcProcessor instance with fast retry config"""
    return GrpcProcessor(timeout=10.0, retry_config=FAST_TEST_RETRY_CONFIG)


@pytest.fixture
def grpc_event() -> Event:
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
async def test_grpc_processor_missing_service(grpc_processor: GrpcProcessor) -> None:
    """Test: Missing service raises ValueError"""
    event = Event(
        id=uuid4(),
        name="grpc_call",
        state=EventState.PENDING,
        payload={"method": "ProcessData"},
    )

    with pytest.raises(ValueError, match="INVALID_GRPC_SERVICE"):
        await grpc_processor.process(event)


@pytest.mark.asyncio
async def test_grpc_processor_missing_method(grpc_processor: GrpcProcessor) -> None:
    """Test: Missing method raises ValueError"""
    event = Event(
        id=uuid4(),
        name="grpc_call",
        state=EventState.PENDING,
        payload={"service": "example.Service"},
    )

    with pytest.raises(ValueError, match="INVALID_GRPC_METHOD"):
        await grpc_processor.process(event)


@pytest.mark.asyncio
async def test_grpc_processor_not_implemented(
    grpc_processor: GrpcProcessor, grpc_event: Event
) -> None:
    """Test: gRPC execution raises NotImplementedError"""
    with pytest.raises(NotImplementedError, match="gRPC processor requires"):
        await grpc_processor.process(grpc_event)


def test_grpc_processor_get_retry_config(grpc_processor: GrpcProcessor) -> None:
    """Test: Retry config with fast test config (injected)"""
    config = grpc_processor.get_retry_config()

    # Using injected FAST_TEST_RETRY_CONFIG
    assert config.max_attempts == FAST_TEST_RETRY_CONFIG.max_attempts
    assert config.initial_backoff == FAST_TEST_RETRY_CONFIG.initial_backoff
    assert config.max_backoff == FAST_TEST_RETRY_CONFIG.max_backoff
    assert config.fast_retry_delay == FAST_TEST_RETRY_CONFIG.fast_retry_delay


def test_grpc_processor_classify_error_permanent() -> None:
    """Test: ValueError classified as PERMANENT"""
    processor = GrpcProcessor(retry_config=FAST_TEST_RETRY_CONFIG)
    error = ValueError("Invalid request")
    assert processor.classify_error(error) == ErrorType.PERMANENT


# ============================================================================
# LocalUseCaseProcessor Tests
# ============================================================================


@pytest.fixture
def local_usecase_processor() -> LocalUseCaseProcessor:
    """Fixture: LocalUseCaseProcessor instance with fast retry config"""
    uow_mock = MagicMock()
    return LocalUseCaseProcessor(uow=uow_mock, retry_config=FAST_TEST_RETRY_CONFIG)


@pytest.fixture
def local_usecase_event() -> Event:
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
async def test_local_usecase_processor_missing_name(
    local_usecase_processor: LocalUseCaseProcessor,
) -> None:
    """Test: Missing use_case_name raises ValueError"""
    event = Event(
        id=uuid4(),
        name="local_usecase",
        state=EventState.PENDING,
        payload={"input": {"data": "test"}},
    )

    with pytest.raises(ValueError, match="MISSING_USECASE_NAME"):
        await local_usecase_processor.process(event)


@pytest.mark.asyncio
async def test_local_usecase_processor_not_implemented(
    local_usecase_processor: LocalUseCaseProcessor, local_usecase_event: Event
) -> None:
    """Test: Local use case execution raises NotImplementedError"""
    with pytest.raises(NotImplementedError, match="Local use case"):
        await local_usecase_processor.process(local_usecase_event)


def test_local_usecase_processor_get_retry_config(
    local_usecase_processor: LocalUseCaseProcessor,
) -> None:
    """Test: Retry config optimized for local execution"""
    config = local_usecase_processor.get_retry_config()

    assert config.max_attempts == FAST_TEST_RETRY_CONFIG.max_attempts
    assert config.initial_backoff == FAST_TEST_RETRY_CONFIG.initial_backoff
    assert config.max_backoff == FAST_TEST_RETRY_CONFIG.max_backoff
    assert config.fast_retry_count == FAST_TEST_RETRY_CONFIG.fast_retry_count
    assert config.fast_retry_delay == FAST_TEST_RETRY_CONFIG.fast_retry_delay


def test_local_usecase_processor_classify_error_permanent() -> None:
    """Test: ValueError classified as PERMANENT"""
    processor = LocalUseCaseProcessor(
        uow=MagicMock(), retry_config=FAST_TEST_RETRY_CONFIG
    )
    error = ValueError("Invalid input")
    assert processor.classify_error(error) == ErrorType.PERMANENT


def test_local_usecase_processor_classify_error_connection() -> None:
    """Test: Connection errors classified as TRANSIENT"""
    processor = LocalUseCaseProcessor(
        uow=MagicMock(), retry_config=FAST_TEST_RETRY_CONFIG
    )
    error = ConnectionError("Cannot connect to DB")
    assert processor.classify_error(error) == ErrorType.TRANSIENT


def test_local_usecase_processor_classify_error_timeout() -> None:
    """Test: Timeout errors classified as TRANSIENT"""
    processor = LocalUseCaseProcessor(
        uow=MagicMock(), retry_config=FAST_TEST_RETRY_CONFIG
    )
    error = TimeoutError("Request timeout")
    assert processor.classify_error(error) == ErrorType.TRANSIENT


# ============================================================================
# Retry Configuration Tests
# ============================================================================


def test_api_processor_faster_than_grpc() -> None:
    """Test: API processor has slower retries than gRPC (API has more backoff)"""
    api_config = ApiCallProcessor().get_retry_config()
    grpc_config = GrpcProcessor().get_retry_config()

    # API has longer initial backoff (network overhead)
    assert api_config.initial_backoff > grpc_config.initial_backoff


def test_local_processor_fastest() -> None:
    """Test: Local processor has fastest retries (local execution is quick)"""
    local_config = LocalUseCaseProcessor(uow=MagicMock()).get_retry_config()
    api_config = ApiCallProcessor().get_retry_config()

    # Local has fewer attempts and shorter backoff
    assert local_config.max_attempts < api_config.max_attempts
    assert local_config.initial_backoff < api_config.initial_backoff
