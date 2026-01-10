import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logconfig import setup_logging

from ..redis.main import broker
from ..redis.main import router as pubsub_router
from .base_router import ExistingRouterAdapter
from .ping_router import PingRouter
from .router_registry import RouterRegistry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # setup app
    setup_logging()
    # setup pubsub readines
    # Asegúrate de que el broker esté conectado
    if (
        not hasattr(broker, "_connection")
        or broker._connection is None
        or broker._connection.connection is None
    ):
        await broker.connect()
        logger.info("Connected to Redis broker has been established.")

    yield
    # TODO: Tear app if needed
    # Close pubsub connections
    await broker.stop()


def bootstrap_api(app: FastAPI, registry: RouterRegistry) -> None:
    for r in registry.get():
        app.include_router(r.router)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(lifespan=lifespan)

    registry = RouterRegistry()
    registry.add(ExistingRouterAdapter(pubsub_router))
    registry.add(PingRouter(pubsub_router.broker))

    bootstrap_api(app, registry)

    return app


app = create_app()
