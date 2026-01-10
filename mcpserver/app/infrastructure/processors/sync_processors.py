"""
Synchronous event processors for request/response operations.

Processors for operations that complete quickly:
- API/REST calls (HTTP)
- gRPC calls
- Local use case execution
"""

import importlib
import logging
from types import ModuleType
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.entities import Event
from app.core.processors import (
    BaseProcessorErrorClassifier,
    ErrorType,
    IEventProcessor,
    ProcessorResult,
    ProcessorResultStatus,
    RetryConfig,
)

logger = logging.getLogger(__name__)

# Optional gRPC support
grpc: ModuleType | None
try:
    grpc = importlib.import_module("grpc")
except ImportError:  # pragma: no cover - optional dependency
    grpc = None


class ApiCallProcessor(IEventProcessor, BaseProcessorErrorClassifier):
    """
    Processor for HTTP/REST API calls.

    Executes async HTTP requests with built-in retry strategy.
    Fast retries for transient failures + exponential backoff.

    Expected event.payload format:
    {
        "method": "GET|POST|PUT|DELETE",
        "url": "https://api.example.com/endpoint",
        "headers": {...},
        "body": {...},
        "timeout": 10  # seconds
    }
    """
    
    # Error classification: ValidationError → permanent, Connection/Timeout → transient
    PERMANENT_EXCEPTIONS = (ValueError,)
    # httpx errors that are transient (should retry)
    TRANSIENT_EXCEPTIONS = (httpx.ConnectError, httpx.TimeoutException)

    def __init__(self, timeout: float = 30.0, retry_config: RetryConfig | None = None):
        """
        Initialize API processor.

        Args:
            timeout: Default timeout for HTTP requests (seconds)
            retry_config: Optional retry configuration (for testing)
        """
        self.timeout = timeout
        self._retry_config = retry_config
        self.logger = logger

    async def process(self, event: Event) -> ProcessorResult:
        """
        Execute HTTP request with retry strategy.

        Args:
            event: Event with API call parameters in payload

        Returns:
            ProcessorResult with HTTP response data

        Raises:
            ValueError: Invalid request parameters
            httpx.RequestError: HTTP request failed (may retry)
        """
        payload = event.payload or {}

        # Validate required fields
        method_str = payload.get("method", "GET")
        if not isinstance(method_str, str):
            raise ValueError("API call requires 'method' to be a string in payload")
        method = method_str.upper()

        url = payload.get("url")
        if not isinstance(url, str):
            raise ValueError("API call requires 'url' to be a string in payload")

        if method not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"):
            raise ValueError(f"Invalid HTTP method: {method}")

        # Extract parameters
        headers_raw = payload.get("headers", {})
        headers: dict[str, str]
        if isinstance(headers_raw, dict):
            headers = {str(k): str(v) for k, v in headers_raw.items()}
        else:
            headers = {}

        body = payload.get("body")
        timeout_value = payload.get("timeout", self.timeout)
        if not isinstance(timeout_value, (int, float)):
            timeout_value = self.timeout
        timeout = float(timeout_value)

        self.logger.info(
            f"API call: {method} {url}",
            extra={
                "event_id": str(event.id),
                "method": method,
                "url": url,
                "timeout": timeout,
            },
        )

        # Execute with retry strategy
        retry_config = self.get_retry_config()
        async_retrying = AsyncRetrying(
            stop=stop_after_attempt(retry_config.max_attempts),
            wait=wait_exponential(
                multiplier=retry_config.backoff_multiplier,
                min=retry_config.initial_backoff,
                max=retry_config.max_backoff,
            ),
            reraise=True,
            # Don't retry PERMANENT errors (ValueError from 4xx HTTP responses)
            retry=retry_if_not_exception_type(ValueError),
        )

        async def _make_request() -> ProcessorResult:
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=body,
                    )
                    response.raise_for_status()

                    return ProcessorResult(
                        status=ProcessorResultStatus.SUCCESS,
                        data={
                            "status_code": response.status_code,
                            "body": response.json() if response.text else None,
                            "headers": dict(response.headers),
                        },
                    )
                except httpx.HTTPStatusError as e:
                    # 4xx errors are permanent, 5xx are transient
                    if 400 <= e.response.status_code < 500:
                        raise ValueError(f"HTTP {e.response.status_code}: {e}")
                    raise

        try:
            async for attempt in async_retrying:
                with attempt:
                    return await _make_request()
        except RetryError as e:
            last_exception = e.last_attempt.exception()
            self.logger.error(
                f"API call failed after retries: {last_exception}",
                extra={"event_id": str(event.id), "url": url},
            )
            if last_exception is not None:
                raise last_exception from e
            raise ValueError("API call failed after retries") from e

        raise RuntimeError("API call did not complete")

    def get_retry_config(self) -> RetryConfig:
        """
        Retry strategy for API calls.

        - 2x fast retries at 100ms (covers ~200ms)
        - 3x exponential backoff: 500ms, 1s, 2s
        - Total p95: ~1700ms

        Returns injected config if provided, else production defaults.
        """
        if self._retry_config is not None:
            return self._retry_config

        return RetryConfig(
            max_attempts=5,
            initial_backoff=0.5,  # 500ms
            max_backoff=2.0,  # 2s
            backoff_multiplier=2.0,
            fast_retry_count=2,
            fast_retry_delay=0.1,  # 100ms
        )

    def classify_error(self, exc: BaseException) -> ErrorType:
        """
        Classify API errors for retry strategy using BaseProcessorErrorClassifier.
        
        HTTP-specific logic:
        - 4xx responses → PERMANENT (raise ValueError)
        - 5xx responses → TRANSIENT (will retry)
        - Connection errors → TRANSIENT (via TRANSIENT_EXCEPTIONS)
        
        Method resolution order:
        1. Check PERMANENT_EXCEPTIONS (ValueError)
        2. Check TRANSIENT_EXCEPTIONS (ConnectError, TimeoutException)
        3. Check HTTPStatusError response code
        4. Default to permanent

        Args:
            exc: Exception raised during API call

        Returns:
            ErrorType (PERMANENT for 4xx, TRANSIENT for others)
        """
        # First check permanent exceptions
        if isinstance(exc, self.PERMANENT_EXCEPTIONS):
            return ErrorType.PERMANENT
        
        # Then check transient exceptions
        if isinstance(exc, self.TRANSIENT_EXCEPTIONS):
            return ErrorType.TRANSIENT
        
        # HTTP Status Error: check response code
        if isinstance(exc, httpx.HTTPStatusError):
            if 400 <= exc.response.status_code < 500:
                return ErrorType.PERMANENT  # 4xx = client error
            return ErrorType.TRANSIENT  # 5xx = server error
        
        # Default to permanent (safe - don't retry unknown errors)
        return ErrorType.PERMANENT


class GrpcProcessor(IEventProcessor, BaseProcessorErrorClassifier):
    """
    Processor for gRPC service calls.

    Executes gRPC methods with retry strategy and timeout.

    Expected event.payload format:
    {
        "service": "package.Service",
        "method": "MethodName",
        "request": {...},
        "address": "localhost:50051",
        "timeout": 10
    }

    Note: This is a skeleton. Actual implementation requires
    gRPC channel management and service stubs.
    """
    
    # Error classification: validation errors are permanent
    PERMANENT_EXCEPTIONS = (ValueError,)

    def __init__(self, timeout: float = 30.0, retry_config: RetryConfig | None = None):
        """
        Initialize gRPC processor.

        Args:
            timeout: Default timeout for gRPC calls (seconds)
            retry_config: Optional retry configuration (for testing)
        """
        self.timeout = timeout
        self._retry_config = retry_config
        self.logger = logger

    async def process(self, event: Event) -> ProcessorResult:
        """
        Execute gRPC call with retry strategy.

        Args:
            event: Event with gRPC call parameters

        Returns:
            ProcessorResult with gRPC response data

        Raises:
            ValueError: Invalid gRPC parameters
            grpc.RpcError: gRPC call failed
        """
        payload = event.payload or {}

        # Validate required fields
        service = payload.get("service")
        method = payload.get("method")
        address = payload.get("address", "localhost:50051")

        if not service or not method:
            raise ValueError("gRPC call requires 'service' and 'method' in payload")

        timeout_value = payload.get("timeout", self.timeout)
        if not isinstance(timeout_value, (int, float)):
            timeout_value = self.timeout
        timeout = float(timeout_value)

        self.logger.info(
            f"gRPC call: {service}.{method}",
            extra={
                "event_id": str(event.id),
                "service": service,
                "method": method,
                "address": address,
                "timeout": timeout,
            },
        )

        # TODO: Implement actual gRPC call execution
        # For now, return placeholder result
        raise NotImplementedError(
            "gRPC processor requires gRPC channel setup. "
            "Implement gRPC stub factory and channel management."
        )

    def get_retry_config(self) -> RetryConfig:
        """
        Retry strategy for gRPC calls.

        Similar to API but slightly faster (gRPC overhead less).

        Returns injected config if provided, else production defaults.
        """
        if self._retry_config is not None:
            return self._retry_config

        return RetryConfig(
            max_attempts=5,
            initial_backoff=0.3,  # 300ms (faster than API)
            max_backoff=2.0,
            backoff_multiplier=2.0,
            fast_retry_count=2,
            fast_retry_delay=0.05,  # 50ms
        )

    def classify_error(self, exc: BaseException) -> ErrorType:
        """
        Classify gRPC errors for retry strategy using BaseProcessorErrorClassifier.
        
        gRPC-specific logic:
        - INVALID_ARGUMENT, NOT_FOUND, PERMISSION_DENIED → PERMANENT
        - UNAVAILABLE, RESOURCE_EXHAUSTED, DEADLINE_EXCEEDED → TRANSIENT
        
        Delegates to parent class for standard cases.

        Args:
            exc: Exception raised during gRPC call

        Returns:
            ErrorType based on gRPC error code
        """
        if grpc is not None and isinstance(exc, grpc.RpcError):
            # Permanent: INVALID_ARGUMENT, NOT_FOUND, PERMISSION_DENIED
            if exc.code() in (
                grpc.StatusCode.INVALID_ARGUMENT,
                grpc.StatusCode.NOT_FOUND,
                grpc.StatusCode.PERMISSION_DENIED,
                grpc.StatusCode.UNAUTHENTICATED,
            ):
                return ErrorType.PERMANENT

            # Transient: UNAVAILABLE, RESOURCE_EXHAUSTED, DEADLINE_EXCEEDED
            if exc.code() in (
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                grpc.StatusCode.DEADLINE_EXCEEDED,
            ):
                return ErrorType.TRANSIENT

        # Delegate to parent for standard cases (ValueError, etc.)
        return super().classify_error(exc)


class LocalUseCaseProcessor(IEventProcessor, BaseProcessorErrorClassifier):
    """
    Processor for local use case execution.

    Executes local async functions with retry strategy.
    Useful for internal business logic that should be async.

    Expected event.payload format:
    {
        "use_case_name": "ProcessOrder",
        "input": {...}
    }

    Requires: UnitOfWork injection to access use cases.
    """
    
    # Error classification: validation errors are permanent
    PERMANENT_EXCEPTIONS = (ValueError, TypeError)

    def __init__(self, uow: Any, retry_config: RetryConfig | None = None):
        """
        Initialize local use case processor.

        Args:
            uow: IUnitOfWork instance for use case execution
            retry_config: Optional retry configuration (for testing)
        """
        self.uow = uow
        self._retry_config = retry_config
        self.logger = logger

    async def process(self, event: Event) -> ProcessorResult:
        """
        Execute local use case with retry strategy.

        Args:
            event: Event with use case name and input

        Returns:
            ProcessorResult with use case output

        Raises:
            ValueError: Invalid use case parameters
            Exception: Use case execution failed
        """
        payload = event.payload or {}

        use_case_name = payload.get("use_case_name")
        raw_input = payload.get("input", {})
        use_case_input = raw_input if isinstance(raw_input, dict) else {}

        if not use_case_name:
            raise ValueError("Local use case requires 'use_case_name' in payload")

        self.logger.info(
            f"Local use case: {use_case_name}",
            extra={
                "event_id": str(event.id),
                "use_case_name": use_case_name,
                "input_keys": list(use_case_input.keys()) if use_case_input else [],
            },
        )

        # TODO: Implement use case registry and execution
        # Map use_case_name → actual use case class
        # Execute with await use_case.execute(input)
        raise NotImplementedError(
            f"Local use case '{use_case_name}' not implemented. "
            "Register use case in LocalUseCaseProcessor."
        )

    def get_retry_config(self) -> RetryConfig:
        """
        Retry strategy for local use cases.

        Fast - local execution should be quick.

        Returns injected config if provided, else production defaults.
        """
        if self._retry_config is not None:
            return self._retry_config

        return RetryConfig(
            max_attempts=3,
            initial_backoff=0.2,  # 200ms
            max_backoff=2.0,
            backoff_multiplier=2.0,
            fast_retry_count=1,
            fast_retry_delay=0.05,  # 50ms
        )

    def classify_error(self, exc: BaseException) -> ErrorType:
        """
        Classify local use case errors using BaseProcessorErrorClassifier.
        
        Local use case-specific logic:
        - ValidationError, ValueError, TypeError → PERMANENT (bugs)
        - Connection/TimeoutError → TRANSIENT (infra issues)
        
        Delegates to parent class for standard classification.

        Args:
            exc: Exception raised during use case execution

        Returns:
            ErrorType based on exception type
        """
        from pydantic import ValidationError
        
        # Local-specific: Connection/Timeout are transient
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return ErrorType.TRANSIENT

        # For other cases including ValidationError, delegate to parent
        # which handles ValueError/TypeError as PERMANENT
        return super().classify_error(exc)
