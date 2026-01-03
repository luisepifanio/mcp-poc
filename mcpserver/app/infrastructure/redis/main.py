import logging
from collections.abc import Awaitable, Callable
from typing import Any

from faststream import AckPolicy, Context, ContextRepo, Depends, FastStream
from faststream.redis import RedisBroker, StreamSub
from faststream.redis.annotations import RedisMessage
from faststream.redis.subscriber.usecases import StreamBatchSubscriber, StreamSubscriber
from result import Ok
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseInput,
    EnqueueEventUseCase,
)

from ..db.connection import get_session
from ..db.unit_of_work import AsyncSQLAlchemyUnitOfWork

logger = logging.getLogger(__name__)
# Configuración del broker de Redis
broker = RedisBroker("redis://localhost:6379")
app = FastStream(broker)


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
    msg: RedisMessage,
) -> None:
    try:
        logger.info(f"Mensaje recibido: {body}")
        # Procesa el mensaje aquí
        await msg.ack()
    except Exception as e:
        logger.error(f"Error al procesar el mensaje: {e}")
        await msg.nack()


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


# Decorador tipado correctamente
EnqueueEventSubscriber: Callable[
    [Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]
] = setup_redis_suscriber("enqueue-event-subject")


@EnqueueEventSubscriber
async def handle_enqueue_event(
    event: EnqueuedEventUseCaseInput,
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        logger.info(f"Evento recibido: {event}")
        # FASE 2: Handler manages transaction context (owns_session=False)
        # UseCase has been refactored to assume caller manages transaction
        # See: docs/TRANSACTION_PATTERN.md
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            usecase = EnqueueEventUseCase(uow)
            result = await usecase.execute(event)
            match result:
                case Ok(value):
                    logger.info(f"Evento encolado con éxito: {value}")
                    # MEJORA #2: TODO - Publish to processing-event-subject here
                    # Once publish is inside context, atomicity is guaranteed
                    await msg.ack()
                case _:
                    logger.error(f"Error al encolar el evento: {result}")
                    await msg.nack()
    except Exception as e:
        logger.error(f"Error al procesar el mensaje: {e}")
        await msg.nack()


# Decorador tipado correctamente
ProcessingEventSubscriber: Callable[
    [Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]
] = setup_redis_suscriber("processing-event-subject")


@ProcessingEventSubscriber
@broker.publisher(stream="result-event-subject")  # <-- listen here
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
