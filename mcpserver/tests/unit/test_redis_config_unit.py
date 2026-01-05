"""Unit tests for Redis broker initialization with settings."""

import os
from unittest.mock import patch

import pytest

from app.core.settings import clearAppSettings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear cached settings before and after each test."""
    clearAppSettings()
    yield
    clearAppSettings()


def test_broker_imports_successfully():
    """Broker module can be imported without errors."""
    from app.infrastructure.redis import main as redis_main

    assert redis_main.broker is not None
    assert redis_main.app is not None


def test_broker_uses_default_url_in_development():
    """In development without explicit config, settings use default localhost:6379."""
    with patch.dict(os.environ, {"ENV": "development"}, clear=True):
        clearAppSettings()
        from app.core.settings import getAppSettings

        settings = getAppSettings(reload=True)

        # Settings should use default values (no local.env loaded in unit test)
        assert "localhost" in settings.redis_connection_url
        assert "6379" in settings.redis_connection_url


def test_broker_uses_custom_redis_url():
    """Settings correctly load custom REDIS_URL from environment."""
    with patch.dict(
        os.environ,
        {"REDIS_URL": "redis://test-redis:6380", "ENV": "test"},
        clear=False,
    ):
        clearAppSettings()
        from app.core.settings import getAppSettings

        settings = getAppSettings(reload=True)

        # Settings should reflect custom URL
        assert "test-redis" in settings.redis_connection_url
        assert "6380" in settings.redis_connection_url


def test_settings_integration_with_redis_module():
    """Redis module correctly integrates with AppSettings."""
    clearAppSettings()
    from app.core.settings import getAppSettings
    from app.infrastructure.redis import main as redis_main

    settings = getAppSettings(reload=True)

    # Both should reference the same configuration
    assert settings.redis_connection_url is not None
    assert redis_main.settings is not None
    # Verify redis module has settings instance
    assert hasattr(redis_main, "settings")


def test_redis_module_has_settings_instance():
    """Redis module exposes settings instance for inspection."""
    from app.infrastructure.redis import main as redis_main

    assert hasattr(redis_main, "settings")
    assert redis_main.settings is not None
    assert hasattr(redis_main.settings, "redis_connection_url")
