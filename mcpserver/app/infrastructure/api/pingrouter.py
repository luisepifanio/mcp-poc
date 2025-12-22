import logging

from faststream.redis import RedisBroker

from app.infrastructure.api.base_router import BaseRouter

logger = logging.getLogger(__name__)


class PingRouter(BaseRouter):
    def __init__(self, redis_broker: RedisBroker) -> None:
        super().__init__()
        self.redis_broker = redis_broker
        # Add the route method to the router
        self._router.add_api_route("/ping", self.ping, methods=["GET"])

    # health check endpoint
    async def ping(self) -> str:
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
