import logging

from faststream.redis import RedisBroker

from .base_router import BaseRouter

logger = logging.getLogger(__name__)


# TODO: Wrap RedisBroker to Abstract Publisher to avoid dependency problems, it is just for testing on redis pubsub


class PingRouter(BaseRouter):
    def __init__(self, broker: RedisBroker) -> None:
        super().__init__()
        self.broker: RedisBroker = broker

    # health check endpoint
    def register_routes(self) -> None:
        """Registra las rutas específicas del router."""

        @self.router.get("/ping")
        async def ping() -> str:  # pyright: ignore[reportUnusedFunction]
            logger.debug("Ping received")
            return "pong"

        @self.router.post("/ping")
        async def ping_post(data: dict[str, object]) -> dict[str, object]:  # pyright: ignore[reportUnusedFunction]
            # await self.broker.publish(
            #     {"message": "Hello FastStream from Gateway Api!"}, stream="demo-subject"
            # )
            return {"message": "Item received", "data": data}
