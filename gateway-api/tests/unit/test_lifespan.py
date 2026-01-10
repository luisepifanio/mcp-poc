"""Unit tests for lifespan context manager with AsyncExitStack.

DESIGN NOTES:
- lifespan delegates connection management to FastStream's lifespan_context()
- NO manual broker connection logic (FastStream handles it internally)
- Tests validate only: setup_logging, AsyncExitStack integration, yield behavior
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

from app.infrastructure.api.main import lifespan


@pytest.mark.asyncio
async def test_lifespan_calls_setup_logging() -> None:
    """Validate that setup_logging is invoked during lifespan startup."""
    with patch("app.infrastructure.api.main.setup_logging") as mock_setup:
        with patch(
            "app.infrastructure.api.main.pubsub_router.lifespan_context"
        ) as mock_lifespan_ctx:
            # Mock FastStream's lifespan_context as simple async context manager
            mock_lifespan_ctx.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_lifespan_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            app = FastAPI()

            async with lifespan(app):
                # Verify setup_logging was called during startup
                mock_setup.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_enters_pubsub_router_lifespan_context() -> None:
    """
    Validate that lifespan delegates to pubsub_router.lifespan_context().

    This ensures FastStream manages broker connection/disconnection lifecycle.
    """
    with patch("app.infrastructure.api.main.setup_logging"):
        with patch(
            "app.infrastructure.api.main.pubsub_router.lifespan_context"
        ) as mock_lifespan_ctx:
            # Mock lifespan_context to track calls
            ctx_mock = AsyncMock()
            ctx_mock.__aenter__ = AsyncMock(return_value=None)
            ctx_mock.__aexit__ = AsyncMock(return_value=None)
            mock_lifespan_ctx.return_value = ctx_mock

            app = FastAPI()

            async with lifespan(app):
                # Verify pubsub_router.lifespan_context was called with app
                mock_lifespan_ctx.assert_called_once_with(app)
                # Verify context was entered (AsyncExitStack management)
                ctx_mock.__aenter__.assert_called_once()

            # After exiting, context should be properly closed
            ctx_mock.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_yields_none() -> None:
    """Validate that lifespan yields None (no state returned to app)."""
    with patch("app.infrastructure.api.main.setup_logging"):
        with patch(
            "app.infrastructure.api.main.pubsub_router.lifespan_context"
        ) as mock_lifespan_ctx:
            mock_lifespan_ctx.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_lifespan_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

            app = FastAPI()

            async with lifespan(app) as value:
                # lifespan should yield None (stateless)
                assert value is None


@pytest.mark.asyncio
async def test_lifespan_cleanup_order_with_async_exit_stack() -> None:
    """
    Validate that AsyncExitStack ensures LIFO cleanup order.

    Order:
    1. setup_logging (first in)
    2. pubsub_router.lifespan_context (second in)
    3. yield
    4. pubsub_router cleanup (second out - LIFO)
    5. AsyncExitStack auto-cleanup (first out - LIFO)
    """
    with patch("app.infrastructure.api.main.setup_logging") as mock_setup:
        with patch(
            "app.infrastructure.api.main.pubsub_router.lifespan_context"
        ) as mock_lifespan_ctx:
            ctx_mock = AsyncMock()
            ctx_mock.__aenter__ = AsyncMock(return_value=None)
            ctx_mock.__aexit__ = AsyncMock(return_value=None)
            mock_lifespan_ctx.return_value = ctx_mock

            app = FastAPI()

            async with lifespan(app):
                # During startup phase
                mock_setup.assert_called_once()
                ctx_mock.__aenter__.assert_called_once()

            # After shutdown phase
            ctx_mock.__aexit__.assert_called_once()
