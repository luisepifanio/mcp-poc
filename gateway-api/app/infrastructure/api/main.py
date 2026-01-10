import logging
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

from app.core.logconfig import setup_logging
from app.infrastructure.publishers import RedisPublisher

# from ..redis.main import broker # Just use broker from pubsub_router
from ..redis.main import router as pubsub_router
from .base_router import ExistingRouterAdapter
from .ping_router import PingRouter
from .router_registry import RouterRegistry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    async with AsyncExitStack() as stack:
        # setup app
        # 1) tu lifespan: logging, bbdd, etc.
        setup_logging()
        # 2) lifespan de FastStream
        await stack.enter_async_context(pubsub_router.lifespan_context(_app))

        yield
        # AsyncExitStack se encarga de cerrar en orden inverso
        # TODO: Tear app if needed
        # Close pubsub connections
        # await broker.stop()


def bootstrap_api(app: FastAPI, registry: RouterRegistry) -> None:
    for r in registry.get():
        app.include_router(r.router)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(lifespan=lifespan)

    # Create publisher implementation
    publisher = RedisPublisher(pubsub_router.broker)

    registry = RouterRegistry()
    registry.add(ExistingRouterAdapter(pubsub_router))
    registry.add(PingRouter(publisher))

    bootstrap_api(app, registry)

    return app


app = create_app()
