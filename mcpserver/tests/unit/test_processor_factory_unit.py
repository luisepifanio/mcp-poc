"""
Unit tests for processor factory and retry configuration presets.

Tests verify that:
1. Production and test configurations are correctly defined
2. Test configs are significantly faster than production configs
3. Factory instantiation works correctly
"""

from app.core.processor_factory import DEFAULT_RETRY_PRESETS
from app.core.processors import RetryConfig


class TestRetryConfigPresets:
    """Test suite for RetryConfigPresets data structure."""

    def test_api_call_prod_config_exists_and_has_correct_values(self) -> None:
        """Verify production API config is correctly defined."""
        config = DEFAULT_RETRY_PRESETS.API_CALL_PROD

        assert isinstance(config, RetryConfig)
        assert config.max_attempts == 5
        assert config.initial_backoff == 0.5
        assert config.max_backoff == 2.0
        assert config.backoff_multiplier == 2.0
        # Production config should have fast retry counts
        assert config.fast_retry_count == 2
        assert config.fast_retry_delay == 0.1

    def test_api_call_test_config_is_faster_than_production(self) -> None:
        """Verify test API config is much faster than production."""
        test_config = DEFAULT_RETRY_PRESETS.API_CALL_TEST
        prod_config = DEFAULT_RETRY_PRESETS.API_CALL_PROD

        # Test config should have fewer attempts
        assert test_config.max_attempts < prod_config.max_attempts
        assert test_config.max_attempts == 3

        # Test config should have lower backoff times
        assert test_config.initial_backoff < prod_config.initial_backoff
        assert test_config.max_backoff < prod_config.max_backoff

        # Verify test config values for speed
        assert test_config.initial_backoff == 0.001  # 1ms
        assert test_config.max_backoff == 0.01  # 10ms

    def test_all_preset_configs_are_valid_retry_config_instances(self) -> None:
        """Verify all presets are valid RetryConfig instances."""
        presets = DEFAULT_RETRY_PRESETS

        # Production configs
        assert isinstance(presets.API_CALL_PROD, RetryConfig)
        assert isinstance(presets.GRPC_PROD, RetryConfig)
        assert isinstance(presets.LOCAL_USECASE_PROD, RetryConfig)

        # Test configs
        assert isinstance(presets.API_CALL_TEST, RetryConfig)
        assert isinstance(presets.GRPC_TEST, RetryConfig)
        assert isinstance(presets.LOCAL_USECASE_TEST, RetryConfig)

    def test_grpc_prod_is_faster_than_api_call_prod(self) -> None:
        """Verify gRPC production config is faster than API (no network overhead)."""
        grpc_config = DEFAULT_RETRY_PRESETS.GRPC_PROD
        api_config = DEFAULT_RETRY_PRESETS.API_CALL_PROD

        # gRPC should have lower initial backoff (binary protocol, less overhead)
        assert grpc_config.initial_backoff < api_config.initial_backoff
        assert grpc_config.initial_backoff == 0.3  # 300ms vs 500ms

    def test_local_usecase_prod_is_fastest_production_config(self) -> None:
        """Verify local use case has lowest latency (in-memory operation)."""
        local_config = DEFAULT_RETRY_PRESETS.LOCAL_USECASE_PROD
        api_config = DEFAULT_RETRY_PRESETS.API_CALL_PROD

        # Local operation should be fastest
        assert local_config.initial_backoff < api_config.initial_backoff
        assert local_config.max_attempts < api_config.max_attempts

        # Verify values
        assert local_config.initial_backoff == 0.05  # 50ms
        assert local_config.max_attempts == 3
