from abc import ABC, abstractmethod

from fastapi import APIRouter


class BaseRouter(ABC):
    def __init__(self) -> None:
        self.router = APIRouter()
        self.register_routes()

    @abstractmethod
    def register_routes(self) -> None:
        """Registra las rutas específicas del router."""
        pass
