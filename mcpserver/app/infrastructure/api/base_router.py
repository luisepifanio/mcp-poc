from fastapi import APIRouter


class BaseRouter:
    def __init__(self) -> None:
        self._router: APIRouter = APIRouter()

    @property
    def router(self) -> APIRouter:
        return self._router
