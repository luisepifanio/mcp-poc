"""Unit tests for lifespan context manager."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI

from app.infrastructure.api.main import lifespan


@pytest.mark.asyncio
async def test_lifespan_setup_logging_is_called() -> None:
    """Validate that setup_logging is invoked during lifespan startup."""
    with patch("app.infrastructure.api.main.setup_logging") as mock_setup:
        app = FastAPI()

        # Enter and exit the context manager
        async with lifespan(app):
            # Verify setup_logging was called during __aenter__
            mock_setup.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_yields_control_to_app() -> None:
    """Validate that lifespan properly yields control during app execution."""
    with patch("app.infrastructure.api.main.setup_logging") as mock_setup:
        app = FastAPI()

        async with lifespan(app) as value:
            # The yield should produce None (no teardown needed currently)
            assert value is None
            # setup_logging should have been called exactly once
            mock_setup.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_multiple_invocations() -> None:
    """Validate that lifespan can be invoked multiple times independently."""
    app = FastAPI()

    with patch("app.infrastructure.api.main.setup_logging") as mock_setup:
        # First invocation
        async with lifespan(app):
            pass

        # Second invocation
        async with lifespan(app):
            pass

        # setup_logging should be called twice
        assert mock_setup.call_count == 2
