import logging
from collections.abc import Awaitable, Callable
from typing import Any

from faststream import (
    AckPolicy,
    Context,  # <--- Importante
)
from faststream.redis import RedisMessage, StreamSub
from faststream.redis.fastapi import RedisRouter
from faststream.redis.subscriber.usecases import StreamBatchSubscriber, StreamSubscriber

from app.core.settings import AppSettings

logger = logging.getLogger(__name__)

settings = AppSettings()

router = RedisRouter(settings.redis_connection_url, setup_state=False)
broker = router.broker


# Define a message handler using the router decorator
def setup_redis_suscriber(
    subject_name: str, min_idle_time: int = 5000, ack_policy: AckPolicy = AckPolicy.MANUAL
) -> StreamSubscriber | StreamBatchSubscriber:
    return broker.subscriber(
        stream=StreamSub(
            subject_name,
            min_idle_time=min_idle_time,
        ),
        ack_policy=ack_policy,
    )


DemoSubscriber: Callable[
    [Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]
] = setup_redis_suscriber("demo-subject")


@DemoSubscriber
async def subscriber_demo(
    body: dict[str, Any],
    msg: RedisMessage = Context(),  # <--- Agrega Context() aquí
) -> None:
    try:
        logger.warning(f"Mensaje recibido: {body}")
        # Procesa el mensaje aquí
        await msg.ack()
    except Exception as e:
        logger.error(f"Error al procesar el mensaje: {e}")
        await msg.nack()
