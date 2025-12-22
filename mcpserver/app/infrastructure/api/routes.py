from collections.abc import Sequence

from fastapi import APIRouter
from faststream.redis.fastapi import RedisRouter

from app.infrastructure.redis.main import broker as redis_broker

from .base_router import BaseRouter
from .pingrouter import PingRouter


def get_routers(
    defaults: Sequence[BaseRouter | APIRouter] | None = None,
) -> Sequence[BaseRouter | APIRouter]:
    return (
        defaults  # defaults includes those mocked for testing environments
        if defaults is not None
        else [
            # production routers go here
            PingRouter(redis_broker),
            RedisRouter(url="redis://localhost:6379"),
        ]
    )
