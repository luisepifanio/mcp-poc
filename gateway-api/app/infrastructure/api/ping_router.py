import logging

from .base_router import BaseRouter

logger = logging.getLogger(__name__)


class PingRouter(BaseRouter):
    def __init__(self) -> None:
        super().__init__()

    # health check endpoint
    def register_routes(self) -> None:
        """Registra las rutas específicas del router."""

        @self.router.get("/ping")
        async def ping() -> str:  # pyright: ignore[reportUnusedFunction]
            logger.info("Ping received")
            return "pong"
