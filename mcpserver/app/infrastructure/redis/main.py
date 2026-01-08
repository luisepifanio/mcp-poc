import logging
from collections.abc import Awaitable, Callable
from typing import Any

from faststream import AckPolicy, Context, ContextRepo, Depends, FastStream
from faststream.redis import RedisBroker, StreamSub
from faststream.redis.annotations import RedisMessage
from faststream.redis.subscriber.usecases import StreamBatchSubscriber, StreamSubscriber
from result import Ok
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    RetryError,
    after_log,
    before_sleep_log,
    stop_after_attempt,
    wait_exponential,
)

from app.core.processor_registry import processor_registry
from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseInput,
    EnqueuedEventUseCaseOutput,
    EnqueueEventUseCase,
)
from app.core.usecases.process_event_usecase import ProcessEventUseCase2

from ...core.settings import getAppSettings
from ..db.connection import get_session
from ..db.unit_of_work import AsyncSQLAlchemyUnitOfWork

logger = logging.getLogger(__name__)

# Get Redis configuration from settings
settings = getAppSettings()
broker = RedisBroker(settings.redis_connection_url)
app = FastStream(broker)

logger.info(f"Redis broker configured: {settings.redis_connection_url}")


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
    """
    Handle incoming events from enqueue-event-subject stream.

    Implements retry strategy with exponential backoff:
    - Enqueue operation: 3 attempts with 1s, 2s, 4s delays
    - Publish operation: 5 attempts with 0.5s, 1s, 2s, 4s, 8s delays

    If all retries fail:
    - Transaction rolls back (atomicity preserved)
    - Message is nack'd for redelivery by Redis

    See: docs/TRANSACTION_PATTERN.md
    See: docs/RETRY_STRATEGY.md (for backoff details)
    """
    try:
        logger.info(f"Evento recibido: {event}")

        # Retry strategy for enqueue operation (save to DB)
        # Max 3 attempts: 1s, 2s, 4s (total ~7s before giving up)
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        ):
            with attempt:
                async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
                    usecase = EnqueueEventUseCase(uow)
                    result = await usecase.execute(event)

                    match result:
                        case Ok(value):
                            logger.info(f"Evento encolado con éxito: {value}")

                            # MEJORA #2 + Retry strategy for publish operation
                            # Max 5 attempts with exponential backoff: 0.5s, 1s, 2s, 4s, 8s
                            # Total ~15.5s before giving up
                            try:
                                async for publish_attempt in AsyncRetrying(
                                    stop=stop_after_attempt(5),
                                    wait=wait_exponential(
                                        multiplier=0.5, min=0.5, max=10
                                    ),
                                    before_sleep=before_sleep_log(
                                        logger, logging.WARNING
                                    ),
                                    after=after_log(logger, logging.INFO),
                                    reraise=True,
                                ):
                                    with publish_attempt:
                                        await broker.publish(
                                            value,
                                            stream="processing-event-subject",
                                        )
                                        logger.info(
                                            f"Evento publicado en processing stream: {value.id}"
                                        )
                            except RetryError as retry_err:
                                # If publish fails after all retries, rollback TX and re-raise
                                logger.error(
                                    f"Publish failed after all retries: {retry_err.last_attempt.exception()}"
                                )
                                raise  # Will trigger TX rollback

                            # Success: both save + publish succeeded
                            await msg.ack()
                        case _:
                            logger.error(f"Error al encolar el evento: {result}")
                            await msg.nack()
                            return  # Exit early, no retry needed for validation errors
    except RetryError as retry_err:
        # Enqueue operation failed after all retries
        logger.error(
            f"Enqueue failed after all retries: {retry_err.last_attempt.exception()}"
        )
        await msg.nack()
    except Exception as e:
        # Unexpected error
        logger.error(f"Error inesperado al procesar el mensaje: {e}", exc_info=True)
        await msg.nack()


# Decorador tipado correctamente
ProcessingEventSubscriber: Callable[
    [Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]
] = setup_redis_suscriber("processing-event-subject")


@ProcessingEventSubscriber
@broker.publisher(stream="result-event-subject")
async def handle_processing_event_queue(
    body: EnqueuedEventUseCaseOutput,
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any] | None:
    """
    Handle event processing orchestration with retry strategy.

    Flow:
    1. Load event from DB
    2. Instantiate ProcessEventUseCase2 with dependencies (UoW, ProcessorRegistry)
    3. Execute with retry strategy (tenacity - exponential backoff)
       - Retries on transient errors
       - Classifies errors via processor.classify_error()
    4. Adapt output to response
    5. Acknowledge/nack message based on result

    Retry logic is encapsulated in infrastructure with tenacity.
    UseCase handles state transitions and processor invocation.
    """
    try:
        logger.info(f"Processing event: {body.id} (name={body.name})")

        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            event_result = await uow.events.getOne(body.id)
            if event_result.is_err():
                logger.error(f"Event {body.id} not found in DB")
                await msg.nack()
                return None

            event = event_result.unwrap()

            # ProcessEventUseCase2 encapsulates retry logic (CORE business logic)
            usecase = ProcessEventUseCase2(uow, processor_registry)
            result = await usecase.execute(event)

            # Handle result
            if result.is_ok():
                processed_event = result.unwrap()
                logger.info(
                    f"Event {body.id} processed successfully: state={processed_event.state}"
                )
                await msg.ack()
                return {
                    "event_id": str(body.id),
                    "status": "success",
                    "state": processed_event.state.value,
                }
            else:
                error = result.unwrap_err()
                logger.error(f"Event {body.id} processing failed: {error.detail}")
                await msg.ack()
                return {
                    "event_id": str(body.id),
                    "status": "error",
                    "error": error.detail,
                }
                logger.info(
                    f"Event {body.id} processed successfully: {processed_event.state}"
                )
                await msg.ack()
                return {
                    "event_id": str(processed_event.id),
                    "state": processed_event.state.value,
                }

            if result and result.is_err():
                error_detail = result.unwrap_err()
                logger.error(f"Event {body.id} processing failed: {error_detail.detail}")
                await msg.ack()
                return {
                    "event_id": str(body.id),
                    "error": error_detail.detail,
                }

            logger.error(f"Event {body.id}: Unknown result state")
            await msg.nack()
            return None

    except Exception as e:
        logger.error(
            f"Unexpected error processing event {body.id}: {e}",
            exc_info=True,
        )
        await msg.nack()
        return None
