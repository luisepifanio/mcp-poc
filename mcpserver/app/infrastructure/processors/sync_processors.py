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
    stop_after_attempt,
    wait_exponential,
)

from app.core.entities import Event
from app.core.processors import (
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


class ApiCallProcessor(IEventProcessor):
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

    def __init__(self, timeout: float = 30.0):
        """
        Initialize API processor.

        Args:
            timeout: Default timeout for HTTP requests (seconds)
        """
        self.timeout = timeout
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
        """
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
        Classify API errors for retry strategy.

        Args:
            exc: Exception raised during API call

        Returns:
            ErrorType (PERMANENT for 4xx, TRANSIENT for others)
        """
        if isinstance(exc, ValueError):
            # Validation errors are permanent
            return ErrorType.PERMANENT
        if isinstance(exc, httpx.HTTPStatusError):
            # 4xx = validation/client error = permanent
            # 5xx = server error = transient
            if 400 <= exc.response.status_code < 500:
                return ErrorType.PERMANENT
            return ErrorType.TRANSIENT
        if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
            return ErrorType.TRANSIENT
        return ErrorType.PERMANENT


class GrpcProcessor(IEventProcessor):
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

    def __init__(self, timeout: float = 30.0):
        """
        Initialize gRPC processor.

        Args:
            timeout: Default timeout for gRPC calls (seconds)
        """
        self.timeout = timeout
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
        """
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
        Classify gRPC errors for retry strategy.

        Args:
            exc: Exception raised during gRPC call

        Returns:
            ErrorType based on gRPC error code
        """
        if isinstance(exc, ValueError):
            return ErrorType.PERMANENT

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

        # Default transient for connection errors
        return ErrorType.TRANSIENT


class LocalUseCaseProcessor(IEventProcessor):
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

    def __init__(self, uow: Any):
        """
        Initialize local use case processor.

        Args:
            uow: IUnitOfWork instance for use case execution
        """
        self.uow = uow
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
        """
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
        Classify local use case errors.

        Args:
            exc: Exception raised during use case execution

        Returns:
            ErrorType based on exception type
        """
        from pydantic import ValidationError

        if isinstance(exc, (ValueError, ValidationError)):
            return ErrorType.PERMANENT

        # Most infrastructure errors are transient
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return ErrorType.TRANSIENT

        # Default: permanent (safe - avoid unnecessary retries)
        return ErrorType.PERMANENT
