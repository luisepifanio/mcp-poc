"""
Processor Factory and Retry Configuration Presets.

This module provides standard retry configurations for different processor types:
- Production configs: Optimized for resilience with appropriate backoff
- Test configs: Fast (< 100ms) to keep unit tests quick

Usage:
    # In production
    config = get_api_call_retry_config()  # 500ms-2s exponential backoff
    
    # In tests
    config = get_api_call_retry_config(fast=True)  # 1ms-10ms fast backoff
"""

from app.core.processors import RetryConfig


# ==================== PRODUCTION CONFIGS ====================
# Optimized for resilience with appropriate backoff times

def get_api_call_retry_config(fast: bool = False) -> RetryConfig:
    """
    Get retry config for API/HTTP calls.
    
    Production: 5 attempts, 500ms-2s exponential backoff (p95 ~1700ms)
    Test: 3 attempts, 1ms-10ms fast backoff (p95 <100ms)
    
    Args:
        fast: If True, return test config; else production config
        
    Returns:
        RetryConfig optimized for API calls
    """
    if fast:
        return RetryConfig(
            max_attempts=3,
            initial_backoff=0.001,    # 1ms
            max_backoff=0.01,         # 10ms
            backoff_multiplier=2.0,
            fast_retry_count=0,
            fast_retry_delay=0,
        )
    else:
        return RetryConfig(
            max_attempts=5,
            initial_backoff=0.5,      # 500ms
            max_backoff=2.0,          # 2s
            backoff_multiplier=2.0,
            fast_retry_count=2,
            fast_retry_delay=0.1,     # 100ms
        )


def get_grpc_retry_config(fast: bool = False) -> RetryConfig:
    """
    Get retry config for gRPC calls.
    
    Production: 5 attempts, 300ms-2s exponential (faster than HTTP, binary protocol)
    Test: 2 attempts, 1ms-5ms fast backoff
    
    Args:
        fast: If True, return test config; else production config
        
    Returns:
        RetryConfig optimized for gRPC calls
    """
    if fast:
        return RetryConfig(
            max_attempts=2,
            initial_backoff=0.001,    # 1ms
            max_backoff=0.005,        # 5ms
            backoff_multiplier=2.0,
            fast_retry_count=0,
            fast_retry_delay=0,
        )
    else:
        return RetryConfig(
            max_attempts=5,
            initial_backoff=0.3,      # 300ms
            max_backoff=2.0,          # 2s
            backoff_multiplier=2.0,
            fast_retry_count=2,
            fast_retry_delay=0.05,    # 50ms
        )


def get_local_usecase_retry_config(fast: bool = False) -> RetryConfig:
    """
    Get retry config for local use case execution.
    
    Production: 3 attempts, 50ms-1s (in-memory operation, fast)
    Test: 2 attempts, 0.1ms-1ms (very fast)
    
    Args:
        fast: If True, return test config; else production config
        
    Returns:
        RetryConfig optimized for local use cases
    """
    if fast:
        return RetryConfig(
            max_attempts=2,
            initial_backoff=0.0001,   # 0.1ms
            max_backoff=0.001,        # 1ms
            backoff_multiplier=2.0,
            fast_retry_count=0,
            fast_retry_delay=0,
        )
    else:
        return RetryConfig(
            max_attempts=3,
            initial_backoff=0.05,     # 50ms
            max_backoff=1.0,          # 1s
            backoff_multiplier=2.0,
            fast_retry_count=0,
            fast_retry_delay=0,
        )


# ==================== PRESETS FOR BACKWARD COMPATIBILITY ====================
# These are used for consistency and testing

class RetryConfigPresets:
    """Container for retry configuration presets (backward compat)."""
    
    API_CALL_PROD = get_api_call_retry_config(fast=False)
    API_CALL_TEST = get_api_call_retry_config(fast=True)
    
    GRPC_PROD = get_grpc_retry_config(fast=False)
    GRPC_TEST = get_grpc_retry_config(fast=True)
    
    LOCAL_USECASE_PROD = get_local_usecase_retry_config(fast=False)
    LOCAL_USECASE_TEST = get_local_usecase_retry_config(fast=True)


# Instantiate singleton for use throughout app
DEFAULT_RETRY_PRESETS = RetryConfigPresets()
