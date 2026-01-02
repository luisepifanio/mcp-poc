import logging

from faststream.redis import RedisBroker

from .base_router import BaseRouter

logger = logging.getLogger(__name__)


class PingRouter(BaseRouter):
    def __init__(self, redis_broker: RedisBroker) -> None:
        self.redis_broker = redis_broker
        super().__init__()

    # health check endpoint
    def register_routes(self) -> None:
        """Registra las rutas específicas del router."""

        @self.router.get("/ping")
        async def ping() -> str:
            logger.info("Ping received")
            # Asegúrate de que el broker esté conectado
            if (
                not hasattr(self.redis_broker, "_connection")
                or self.redis_broker._connection is None
                or self.redis_broker._connection.connection is None
            ):
                await self.redis_broker.connect()

            await self.redis_broker.publish(
                {"message": "Hi there from /ping endpoint"}, stream="in-subject"
            )

            return "pong"
