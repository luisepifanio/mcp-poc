from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_startup_connects_when_not_connected() -> None:
    # Import function and broker, then patch broker.connect and set disconnected state
    from app.infrastructure.redis.main import broker, startup

    broker._connection = None
    with patch.object(broker, "connect", new_callable=AsyncMock) as mock_connect:
        context = MagicMock()
        await startup(context)

        mock_connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_skips_connect_when_already_connected() -> None:
    from app.infrastructure.redis.main import broker, startup

    conn = MagicMock()
    conn.connection = "fake"
    broker._connection = conn

    with patch.object(broker, "connect", new_callable=AsyncMock) as mock_connect:
        context = MagicMock()
        await startup(context)

        mock_connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscriber_demo_ack_on_success() -> None:
    from app.infrastructure.redis.main import subscriber_demo

    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()

    body = {"message": "Hi there from /ping endpoint"}

    await subscriber_demo(body, msg)

    msg.ack.assert_awaited_once()
    msg.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscriber_demo_ack_on_exception() -> None:
    from app.infrastructure.redis.main import subscriber_demo

    msg = MagicMock()
    # Force ack to raise to hit exception path
    msg.ack = AsyncMock(side_effect=Exception("boom"))
    msg.nack = AsyncMock()

    body = {"message": "Hi there"}

    await subscriber_demo(body, msg)

    msg.nack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_processing_event_queue_ack_on_success() -> None:
    """Test that ack is called on successful processing.

    NOTE: This is a simplified unit test that mocks dependencies.
    For full integration testing, see functional tests.
    """
    from unittest.mock import AsyncMock, MagicMock, patch
    from uuid import uuid4

    from result import Ok

    from app.core.entities import Event, EventState
    from app.core.usecases.event_usecases import EnqueuedEventUseCaseOutput
    from app.infrastructure.redis.main import handle_processing_event_queue

    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()

    session_mock = AsyncMock()

    test_event = Event(
        id=uuid4(),
        name="test_event",
        state=EventState.PENDING,
        payload={"test": "data"},
    )

    with patch(
        "app.infrastructure.redis.main.AsyncSQLAlchemyUnitOfWork"
    ) as uow_mock_class:
        uow_mock = AsyncMock()
        uow_mock.__aenter__.return_value = uow_mock
        uow_mock.__aexit__.return_value = None
        uow_mock.events.getOne = AsyncMock(return_value=Ok(test_event))

        with patch("app.infrastructure.redis.main.processor_registry") as registry_mock:
            processor_mock = MagicMock()
            processor_mock.get_retry_config.return_value = MagicMock(
                max_attempts=1,
                initial_backoff=0.0,
                max_backoff=0.0,
                backoff_multiplier=1.0,
            )
            processor_mock.process = AsyncMock(
                return_value=MagicMock(
                    status=MagicMock(value="success"), data={"result": "ok"}
                )
            )
            registry_mock.get.return_value = processor_mock

            with patch(
                "app.infrastructure.redis.main.ProcessEventUseCase2"
            ) as usecase_mock_class:
                usecase_mock = MagicMock()
                usecase_mock.execute = AsyncMock(
                    return_value=Ok(
                        EnqueuedEventUseCaseOutput(
                            id=test_event.id,
                            name="test_event",
                            payload=test_event.payload,
                            state=EventState.COMPLETED,
                        )
                    )
                )
                usecase_mock_class.return_value = usecase_mock
                uow_mock_class.return_value = uow_mock

                body = EnqueuedEventUseCaseOutput(
                    id=test_event.id,
                    name="test_event",
                    payload={"test": "data"},
                    state=EventState.PENDING,
                )

                result = await handle_processing_event_queue(body, msg, session_mock)

                msg.ack.assert_awaited_once()
                msg.nack.assert_not_awaited()
                assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_handle_processing_event_queue_nack_on_event_not_found() -> None:
    """Test that nack is called when event is not found."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.infrastructure.redis.main import handle_processing_event_queue

    msg = MagicMock()
    msg.ack = AsyncMock()
    msg.nack = AsyncMock()

    session_mock = AsyncMock()

    # Mock the UnitOfWork to simulate event not found
    with patch(
        "app.infrastructure.redis.main.AsyncSQLAlchemyUnitOfWork"
    ) as uow_mock_class:
        uow_mock = AsyncMock()
        uow_mock.__aenter__.return_value = uow_mock
        uow_mock.__aexit__.return_value = None

        # Mock getOne() to return Err (event not found)
        from result import Err

        from app.errors import ErrorCatalog, ErrorDetail

        uow_mock.events.getOne = AsyncMock(
            return_value=Err(
                ErrorDetail(error=ErrorCatalog.NOT_FOUND.value, detail="Event not found")
            )
        )
        uow_mock_class.return_value = uow_mock

        from uuid import uuid4

        from app.core.entities import EventState
        from app.core.usecases.event_usecases import (
            EnqueuedEventUseCaseOutput,
        )

        body = EnqueuedEventUseCaseOutput(
            id=uuid4(),
            name="test_event",
            payload={},
            state=EventState.PENDING,
        )

        result = await handle_processing_event_queue(body, msg, session_mock)

        msg.nack.assert_awaited_once()
        assert result is None
