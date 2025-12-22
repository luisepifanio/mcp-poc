import logging
from typing import Any

from faststream import AckPolicy, Context, ContextRepo, FastStream
from faststream.redis import RedisBroker, StreamSub
from faststream.redis.annotations import Redis, RedisMessage

from app.core.usecases.event_usecases import EventUseCaseInput, EventUseCaseOutput

logger = logging.getLogger(__name__)
# Configuración del broker de Redis
broker = RedisBroker("redis://localhost:6379")
app = FastStream(broker)


@app.on_startup
async def startup(context: ContextRepo) -> None:
    logger.info(f"Starting redis, connecting \n {context}")
    # context.set_global("model", ml_models)
    if (
        not hasattr(broker, "_connection")
        or broker._connection is None
        or broker._connection.connection is None
    ):
        await broker.connect()
        logger.info(f"redis connected: {broker._connection}")


@app.on_shutdown
async def shutdown(context: Any = Context()) -> None:
    logger.info(f"Shutting redis\n {context}")


@broker.subscriber(
    stream=StreamSub(
        "in-subject",  # Nombre del stream
        min_idle_time=5000,  # Tiempo mínimo de inactividad en milisegundos (5 segundos)
    ),
    ack_policy=AckPolicy.MANUAL,  # Política de reconocimiento manual
)  # type: ignore[misc]
async def handle_incoming_enqueue_event(
    body: dict[str, Any],
    msg: RedisMessage,
) -> None:
    try:
        logger.info(f"Mensaje recibido: {body}")
        # Procesa el mensaje aquí
        await msg.ack()
    except Exception as e:
        logger.error(f"Error al procesar el mensaje: {e}")
        await msg.nack()


@broker.subscriber(
    stream=StreamSub(
        "processing-subject",
        min_idle_time=5000,  # 5 seconds
    ),
    ack_policy=AckPolicy.MANUAL,
)  # type: ignore[misc]
@broker.publisher(stream="out-subject")  # <-- listen here  # type: ignore[misc]
async def handle_processing_event_queue(
    body: dict[str, Any],
    msg: RedisMessage,
) -> dict[str, Any] | None:
    try:
        # Process the claimed message
        logger.info(f"Mensaje recibido: {body} as part of {msg} ")
        # Explicitly acknowledge after successful processing
        # Manually acknowledge the message
        await msg.ack()
        return {"processed_data": body}
    except Exception as e:
        # or, if processing fails and you want to reprocess later
        await msg.nack()
        logger.error(f"Failed to process: {e}")
        return None
