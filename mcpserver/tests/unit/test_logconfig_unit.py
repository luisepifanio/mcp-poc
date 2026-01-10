"""Unit tests for logging configuration module."""

import os
from unittest.mock import patch


def test_logconfig_imports_successfully():
    """Verify logconfig module can be imported without errors."""
    from app.core import logconfig

    assert logconfig.ENV is not None
    assert logconfig.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def test_logconfig_env_detects_production():
    """Verify ENV detection for production environment."""
    with patch.dict(os.environ, {"ENV": "production"}):
        # Re-import to get new ENV value
        import importlib

        from app.core import logconfig

        importlib.reload(logconfig)
        assert logconfig.ENV == "production"


def test_logconfig_env_detects_development():
    """Verify ENV detection for development environment."""
    with patch.dict(os.environ, {"ENV": "development"}):
        import importlib

        from app.core import logconfig

        importlib.reload(logconfig)
        assert logconfig.ENV == "development"


def test_logconfig_log_level_configuration():
    """Verify LOG_LEVEL configuration from environment."""
    with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
        import importlib

        from app.core import logconfig

        importlib.reload(logconfig)
        assert logconfig.LOG_LEVEL == "DEBUG"


def test_logconfig_formatters_defined():
    """Verify logging formatters are properly defined."""
    from app.core import logconfig

    # Development formatter should use colorlog
    assert "DEV_FORMATTER" in dir(logconfig)
    assert logconfig.DEV_FORMATTER is not None
    assert logconfig.DEV_FORMATTER.get("()") == "colorlog.ColoredFormatter"

    # Production formatter should use JSON
    assert "PROD_FORMATTER" in dir(logconfig)
    assert logconfig.PROD_FORMATTER is not None
    assert logconfig.PROD_FORMATTER.get("()") == "pythonjsonlogger.json.JsonFormatter"


def test_logconfig_handlers_configured():
    """Verify logging handlers are properly configured."""
    from app.core import logconfig

    # Check that get_logging_config returns a properly structured config
    assert hasattr(logconfig, "get_logging_config")
    config = logconfig.get_logging_config()
    assert config is not None
    assert "handlers" in config
    assert "default" in config["handlers"]


def test_logconfig_root_logger_configured():
    """Verify root logger is properly configured."""
    from app.core import logconfig

    config = logconfig.get_logging_config()
    assert "loggers" in config
    assert "" in config["loggers"]  # Root logger
    assert "handlers" in config["loggers"][""]
    assert "level" in config["loggers"][""]


def test_logconfig_setup_logging_runs_without_error():
    """Call setup_logging to cover logging configuration path."""
    from app.core import logconfig

    # Should not raise when applying dictConfig
    logconfig.setup_logging()
