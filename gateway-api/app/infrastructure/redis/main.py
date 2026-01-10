import logging
from typing import Annotated, Any

from faststream import AckPolicy
from faststream.redis import RedisMessage, StreamSub
from faststream.redis.fastapi import Context, RedisRouter

from app.core.settings import AppSettings

logger = logging.getLogger(__name__)

settings = AppSettings()

router = RedisRouter(settings.redis_connection_url, setup_state=False)
broker = router.broker


# IMPORTANT!
# 1. En lugar de usar la función decoradora DemoSubscriber, usa el router directamente
# 2. msg: Annotated[RedisMessage, Context("message")], # <--- aqui es requerido el naming
# 3. Solo ignora los problemas de typing, con esto funciona  # type: ignore
@router.subscriber(  # type: ignore
    stream=StreamSub("demo-subject", min_idle_time=5000),
    ack_policy=AckPolicy.MANUAL,
)
async def subscriber_demo(
    body: dict[str, Any],
    # Ahora usamos el Context compatible con FastAPI
    msg: Annotated[RedisMessage, Context("message")],  # <--- name parameter required
) -> None:
    try:
        logger.warning(f"Mensaje recibido: {body}")
        # Procesa el mensaje aquí
        await msg.ack()
    except Exception as e:
        logger.error(f"Error al procesar el mensaje: {e}")
        await msg.nack()
