"""Unit tests for Redis configuration in AppSettings."""

import os
from unittest.mock import patch

import pytest

from app.core.settings import AppSettings, clearAppSettings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear cached settings before and after each test."""
    clearAppSettings()
    yield
    clearAppSettings()


def test_redis_connection_url_default():
    """Default redis_url is used directly when not customized."""
    with patch.dict(os.environ, {"ENV": "production"}, clear=True):
        clearAppSettings()
        settings = AppSettings()
        # When no override, uses model default of 6379
        assert settings.redis_connection_url == "redis://localhost:6379/0"


def test_redis_connection_url_custom_url():
    """Custom redis_url has priority over individual components."""
    with patch.dict(os.environ, {"REDIS_URL": "redis://custom-host:9999"}, clear=False):
        clearAppSettings()
        settings = AppSettings()
        assert settings.redis_connection_url == "redis://custom-host:9999"


def test_redis_connection_url_from_components_no_password():
    """Build URL from components (host/port/db) without password."""
    with patch.dict(
        os.environ,
        {
            "REDIS_HOST": "prod-redis",
            "REDIS_PORT": "6380",
            "REDIS_DB": "2",
            "ENV": "production",  # Avoid loading test.env
        },
        clear=True,
    ):
        clearAppSettings()
        settings = AppSettings()
        # redis_url is still default, so build from components
        assert settings.redis_connection_url == "redis://prod-redis:6380/2"


def test_redis_connection_url_from_components_with_password():
    """Build URL from components including password authentication."""
    with patch.dict(
        os.environ,
        {
            "REDIS_HOST": "secure-redis",
            "REDIS_PORT": "6379",
            "REDIS_PASSWORD": "super-secret",
            "REDIS_DB": "1",
            "ENV": "production",
        },
        clear=True,
    ):
        clearAppSettings()
        settings = AppSettings()
        assert (
            settings.redis_connection_url == "redis://:super-secret@secure-redis:6379/1"
        )


def test_redis_connection_url_custom_url_ignores_components():
    """When redis_url is customized, individual components are ignored."""
    with patch.dict(
        os.environ,
        {
            "REDIS_URL": "redis://explicit-url:7777",
            "REDIS_HOST": "ignored-host",
            "REDIS_PORT": "9999",
        },
        clear=False,
    ):
        clearAppSettings()
        settings = AppSettings()
        # redis_url takes priority
        assert settings.redis_connection_url == "redis://explicit-url:7777"


def test_redis_fields_default_values():
    """Verify default values for all Redis configuration fields."""
    with patch.dict(os.environ, {"ENV": "production"}, clear=True):
        clearAppSettings()
        settings = AppSettings()
        # Model defaults to 6379
        assert settings.redis_url == "redis://localhost:6379"
    assert settings.redis_host == "localhost"
    assert settings.redis_port == 6379
    assert settings.redis_db == 0
    assert settings.redis_password is None


def test_redis_password_optional():
    """Redis password is optional and can be None."""
    with patch.dict(os.environ, {"REDIS_HOST": "localhost"}, clear=False):
        clearAppSettings()
        settings = AppSettings()
        assert settings.redis_password is None
        # URL should not include auth section
        assert "@" not in settings.redis_connection_url


def test_redis_db_integer():
    """Redis DB must be an integer."""
    with patch.dict(os.environ, {"REDIS_DB": "5"}, clear=False):
        clearAppSettings()
        settings = AppSettings()
        assert settings.redis_db == 5
        assert isinstance(settings.redis_db, int)


def test_redis_port_integer():
    """Redis port must be an integer."""
    with patch.dict(os.environ, {"REDIS_PORT": "6380"}, clear=False):
        clearAppSettings()
        settings = AppSettings()
        assert settings.redis_port == 6380
        assert isinstance(settings.redis_port, int)
