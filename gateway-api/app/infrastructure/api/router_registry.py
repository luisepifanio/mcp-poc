# app/infrastructure/api/router_registry.py
from collections.abc import Iterable

from .base_router import BaseRouter


class RouterRegistry:
    def __init__(self) -> None:
        self._routers: list[BaseRouter] = []

    def add(self, router: BaseRouter) -> None:
        self._routers.append(router)

    def get(self) -> Iterable[BaseRouter]:
        return tuple(self._routers)
