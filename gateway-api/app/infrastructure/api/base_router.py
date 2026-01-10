from abc import ABC, abstractmethod

from fastapi import APIRouter


class BaseRouter(ABC):
    def __init__(self, router: APIRouter | None = None) -> None:
        self.router = router or APIRouter()
        self.register_routes()

    @abstractmethod
    def register_routes(self) -> None:
        """Registra las rutas específicas del router."""
        pass


class ExistingRouterAdapter(BaseRouter):
    def __init__(self, existing_router: APIRouter) -> None:
        super().__init__(router=existing_router)

    def register_routes(self) -> None:
        pass  # No need to register new routes if Existing
        # for route in self.existing_router.routes:
        #     self.router.routes.append(route)
