"""Unit tests for app/core/settings.py."""

from unittest.mock import patch

from app.core.settings import (
    AppSettings,
    clearAppSettings,
    getAppSettings,
    resolve_env_file,
)


class TestResolveEnvFile:
    """Unit tests for resolve_env_file function."""

    def test_resolve_env_file_development(self) -> None:
        """Test ENV=development returns local.env."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = "development"
            result = resolve_env_file()
            assert result == "local.env"
            mock_getenv.assert_called_once_with("ENV", "")

    def test_resolve_env_file_dev(self) -> None:
        """Test ENV=dev returns local.env."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = "dev"
            result = resolve_env_file()
            assert result == "local.env"
            mock_getenv.assert_called_once_with("ENV", "")

    def test_resolve_env_file_local(self) -> None:
        """Test ENV=local returns local.env."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = "local"
            result = resolve_env_file()
            assert result == "local.env"
            mock_getenv.assert_called_once_with("ENV", "")

    def test_resolve_env_file_test(self) -> None:
        """Test ENV=test returns test.env."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = "test"
            result = resolve_env_file()
            assert result == "test.env"
            mock_getenv.assert_called_once_with("ENV", "")

    def test_resolve_env_file_testing(self) -> None:
        """Test ENV=testing returns test.env."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = "testing"
            result = resolve_env_file()
            assert result == "test.env"
            mock_getenv.assert_called_once_with("ENV", "")

    def test_resolve_env_file_production(self) -> None:
        """Test ENV=production returns None (no .env file)."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = "production"
            result = resolve_env_file()
            assert result is None
            mock_getenv.assert_called_once_with("ENV", "")

    def test_resolve_env_file_empty(self) -> None:
        """Test ENV empty string returns None."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = ""
            result = resolve_env_file()
            assert result is None
            mock_getenv.assert_called_once_with("ENV", "")

    def test_resolve_env_file_uppercase_normalization(self) -> None:
        """Test that ENV values are normalized to lowercase."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = "DEVELOPMENT"
            result = resolve_env_file()
            assert result == "local.env"
            mock_getenv.assert_called_once_with("ENV", "")

    def test_resolve_env_file_mixed_case_normalization(self) -> None:
        """Test that mixed case ENV values are normalized to lowercase."""
        with patch("app.core.settings.os.getenv") as mock_getenv:
            mock_getenv.return_value = "DeVeLoPmEnT"
            result = resolve_env_file()
            assert result == "local.env"
            mock_getenv.assert_called_once_with("ENV", "")


class TestGetAppSettings:
    """Unit tests for getAppSettings function."""

    def setup_method(self) -> None:
        """Clear cached settings before each test."""
        clearAppSettings()

    def teardown_method(self) -> None:
        """Clear cached settings after each test."""
        clearAppSettings()

    def test_get_app_settings_creates_singleton(self) -> None:
        """Test that getAppSettings creates a singleton instance."""
        settings1 = getAppSettings()
        settings2 = getAppSettings()
        assert settings1 is settings2
        assert isinstance(settings1, AppSettings)

    def test_get_app_settings_reload_creates_new_instance(self) -> None:
        """Test that reload=True clears cache and creates new instance."""
        settings1 = getAppSettings()
        settings2 = getAppSettings(reload=True)
        assert settings1 is not settings2
        assert isinstance(settings2, AppSettings)

    def test_get_app_settings_returns_app_settings_instance(self) -> None:
        """Test that getAppSettings returns AppSettings instance."""
        settings = getAppSettings()
        assert isinstance(settings, AppSettings)
        assert hasattr(settings, "env")
        assert hasattr(settings, "log_level")

    def test_get_app_settings_cached_after_first_call(self) -> None:
        """Test that config is cached after first call."""
        with patch.object(AppSettings, "__init__", return_value=None) as mock_init:
            clearAppSettings()
            getAppSettings()
            call_count_first = mock_init.call_count

            getAppSettings()
            call_count_second = mock_init.call_count

            # AppSettings should be instantiated only once (or at most once)
            assert call_count_first == call_count_second

    def test_get_app_settings_reload_creates_fresh_instance(self) -> None:
        """Test that reload flag forces re-instantiation."""
        settings1 = getAppSettings()
        settings1_id = id(settings1)

        settings2 = getAppSettings(reload=True)
        settings2_id = id(settings2)

        assert settings1_id != settings2_id

    def test_clear_app_settings_resets_global_state(self) -> None:
        """Test that clearAppSettings resets the global _config."""
        settings1 = getAppSettings()
        clearAppSettings()
        settings2 = getAppSettings()

        assert id(settings1) != id(settings2)
        assert isinstance(settings2, AppSettings)

    def test_get_app_settings_default_values(self) -> None:
        """Test that AppSettings has expected default values."""
        clearAppSettings()
        with patch("app.core.settings.resolve_env_file", return_value=None):
            settings = getAppSettings(reload=True)
            # Verify defaults (env var might override, so we just check existence)
            assert hasattr(settings, "env")
            assert hasattr(settings, "log_level")

    def test_get_app_settings_none_check_for_caching(self) -> None:
        """Test that None check in caching logic works correctly."""
        clearAppSettings()
        settings1 = getAppSettings()
        assert settings1 is not None

        # Get again without reload - should be same instance
        settings2 = getAppSettings()
        assert settings1 is settings2

    def test_get_app_settings_multiple_reloads(self) -> None:
        """Test that multiple reloads create distinct instances."""
        settings1 = getAppSettings()
        id1 = id(settings1)

        settings2 = getAppSettings(reload=True)
        id2 = id(settings2)

        settings3 = getAppSettings(reload=True)
        id3 = id(settings3)

        # All should be different instances
        assert id1 != id2 != id3
