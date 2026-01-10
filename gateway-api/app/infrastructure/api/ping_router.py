import logging

from app.core.publisher import IPublisher
from app.core.types import JSONValue

from .base_router import BaseRouter

logger = logging.getLogger(__name__)


class PingRouter(BaseRouter):
    def __init__(self, publisher: IPublisher) -> None:
        super().__init__()
        self.publisher = publisher

    # health check endpoint
    def register_routes(self) -> None:
        """Registra las rutas específicas del router."""

        @self.router.get("/ping")
        async def ping() -> str:  # pyright: ignore[reportUnusedFunction]
            logger.debug("Ping received")
            return "pong"

        @self.router.post("/ping")
        async def ping_post(
            data: dict[str, object],
        ) -> dict[str, object]:  # pyright: ignore[reportUnusedFunction]
            message: JSONValue = {"message": "Hello FastStream from Gateway Api!"}

            result = await self.publisher.publish(message, stream="demo-subject")
            if result.is_err():
                logger.error(f"Failed to publish message: {result.unwrap_err()}")
            return {"message": "Item received", "data": data}
