import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logconfig import setup_logging

from .ping_router import PingRouter
from .router_registry import RouterRegistry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # setup app
    setup_logging()
    yield
    # TODO: Tear app if needed


def bootstrap_api(app: FastAPI, registry: RouterRegistry) -> None:
    for r in registry.get():
        app.include_router(r.router)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(lifespan=lifespan)

    registry = RouterRegistry()
    registry.add(PingRouter())

    bootstrap_api(app, registry)

    return app


app = create_app()
