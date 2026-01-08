"""Unit tests for BaseRouter and RouterRegistry."""

from fastapi import APIRouter

from app.infrastructure.api.base_router import BaseRouter
from app.infrastructure.api.router_registry import RouterRegistry


class MockRouter(BaseRouter):
    """Mock router for testing BaseRouter."""

    def register_routes(self) -> None:
        """Register a test route."""

        @self.router.get("/test")
        async def test_route() -> str:  # pyright: ignore[reportUnusedFunction]
            return "test"


class TestBaseRouter:
    """Unit tests for BaseRouter abstract class."""

    def test_base_router_creates_api_router(self) -> None:
        """Test that BaseRouter creates an APIRouter instance."""
        router = MockRouter()
        assert isinstance(router.router, APIRouter)

    def test_base_router_calls_register_routes(self) -> None:
        """Test that __init__ calls register_routes."""
        router = MockRouter()
        # If register_routes was called, router should have routes
        assert len(router.router.routes) > 0


class TestRouterRegistry:
    """Unit tests for RouterRegistry."""

    def test_router_registry_is_empty_on_creation(self) -> None:
        """Test that RouterRegistry starts with no routers."""
        registry = RouterRegistry()
        routers = list(registry.get())
        assert len(routers) == 0

    def test_router_registry_add_single_router(self) -> None:
        """Test adding a single router to registry."""
        registry = RouterRegistry()
        router = MockRouter()
        registry.add(router)
        routers = list(registry.get())
        assert len(routers) == 1
        assert routers[0] is router

    def test_router_registry_add_multiple_routers(self) -> None:
        """Test adding multiple routers to registry."""
        registry = RouterRegistry()
        router1 = MockRouter()
        router2 = MockRouter()
        registry.add(router1)
        registry.add(router2)
        routers = list(registry.get())
        assert len(routers) == 2
        assert routers[0] is router1
        assert routers[1] is router2

    def test_router_registry_returns_iterable(self) -> None:
        """Test that get() returns an iterable."""
        registry = RouterRegistry()
        router = MockRouter()
        registry.add(router)
        result = registry.get()
        # Should be iterable
        assert hasattr(result, "__iter__")
