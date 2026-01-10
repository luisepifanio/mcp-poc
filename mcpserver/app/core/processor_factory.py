"""
Processor Factory and Retry Configuration Presets.

This module provides:
- RetryConfigPresets: Standard retry configurations for different processor types
- ProcessorFactory: Factory for creating processors with consistent configuration

Purpose:
- Centralize retry configuration (DRY principle)
- Ensure test processors are fast, production processors are resilient
- Make processor creation consistent across codebase
"""

from dataclasses import dataclass

from .processors import RetryConfig


@dataclass(frozen=True)
class RetryConfigPresets:
    """Standard retry configurations for different processor types.
    
    Production configs are optimized for resilience with appropriate backoff.
    Test configs are fast to keep unit tests under 1s.
    """
    
    # ==================== PRODUCTION CONFIGS ====================
    # API Call: HTTP calls with 5 attempts, 100ms-2s exponential backoff
    # p95 latency: ~1700ms (500ms + 1s + 2s + timeouts)
    API_CALL_PROD: "RetryConfig" = RetryConfig(
        max_attempts=5,
        initial_backoff=0.5,      # 500ms
        max_backoff=2.0,          # 2s
        backoff_multiplier=2.0,   # Exponential: 500ms → 1s → 2s
        fast_retry_count=2,
        fast_retry_delay=0.1,     # 100ms (not used in exponential)
    )
    
    # gRPC Call: Similar to API but faster overhead (binary protocol)
    # p95 latency: ~1300ms
    GRPC_PROD: "RetryConfig" = RetryConfig(
        max_attempts=5,
        initial_backoff=0.3,      # 300ms (faster than HTTP)
        max_backoff=2.0,          # 2s
        backoff_multiplier=2.0,
        fast_retry_count=2,
        fast_retry_delay=0.05,    # 50ms
    )
    
    # Local Use Case: In-memory operation, fewer retries
    # p95 latency: ~150ms
    LOCAL_USECASE_PROD: "RetryConfig" = RetryConfig(
        max_attempts=3,
        initial_backoff=0.05,     # 50ms (in-memory, fast)
        max_backoff=1.0,          # 1s
        backoff_multiplier=2.0,
        fast_retry_count=0,
        fast_retry_delay=0,
    )
    
    # ==================== TEST CONFIGS (FAST) ====================
    # Test configs are optimized for speed: minimal retries, no backoff
    # All test configs complete in <100ms
    
    API_CALL_TEST: "RetryConfig" = RetryConfig(
        max_attempts=3,
        initial_backoff=0.001,    # 1ms
        max_backoff=0.01,         # 10ms
        backoff_multiplier=2.0,
        fast_retry_count=0,
        fast_retry_delay=0,
    )
    
    GRPC_TEST: "RetryConfig" = RetryConfig(
        max_attempts=2,
        initial_backoff=0.001,    # 1ms
        max_backoff=0.005,        # 5ms
        backoff_multiplier=2.0,
        fast_retry_count=0,
        fast_retry_delay=0,
    )
    
    LOCAL_USECASE_TEST: "RetryConfig" = RetryConfig(
        max_attempts=2,
        initial_backoff=0.0001,   # 0.1ms
        max_backoff=0.001,        # 1ms
        backoff_multiplier=2.0,
        fast_retry_count=0,
        fast_retry_delay=0,
    )


# Instantiate singleton for use throughout app
DEFAULT_RETRY_PRESETS = RetryConfigPresets()
