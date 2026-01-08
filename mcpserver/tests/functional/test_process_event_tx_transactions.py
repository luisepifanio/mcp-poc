import asyncio
from uuid import uuid4

import pytest
from result import Ok

from app.core.entities import Event, EventState
from app.core.processor_registry import processor_registry
from app.core.processors import (
    IEventProcessor,
    ProcessorResult,
    ProcessorResultStatus,
    RetryConfig,
)
from app.core.usecases.event_usecases import EnqueuedEventUseCaseOutput
from app.core.usecases.neo_event_usecase import ProcessEventIdealUseCase


@pytest.mark.asyncio
async def test_tx1_and_tx2_persisted(uow_factory):
    """
    E2E test that validates two transaction boundaries:
    - TX1: validate_and_lock persists PROCESSING before processor runs
    - TX2: persist_outcome persists COMPLETED after processing
    The test registers a short processor that reads the DB during `process()`
    to observe the state persisted by TX1.
    """

    observed_states: list[EventState] = []

    class TxTestProcessor(IEventProcessor):
        async def process(self, event: Event) -> ProcessorResult:
            # Inspect DB state using new session factory to ensure we read
            # the state as persisted by the earlier transaction (TX1).
            from app.infrastructure.db.connection import get_session_local

            AsyncSessionLocal = await get_session_local()
            async with AsyncSessionLocal() as session:
                db_ev = await session.get(Event, event.id)
                observed_states.append(db_ev.state)

            return ProcessorResult(
                status=ProcessorResultStatus.SUCCESS, data={"ok": True}
            )

        def get_retry_config(self) -> RetryConfig:  # type: ignore[override]
            return RetryConfig(
                max_attempts=1,
                initial_backoff=0.0,
                max_backoff=0.0,
                backoff_multiplier=1.0,
            )

    # Create and save initial event (enqueue) in DB
    evt = Event(
        id=uuid4(),
        name="evt",
        external_uuid=None,
        payload={},
        context={},
        state=EventState.PENDING,
    )

    async with uow_factory() as uow:
        saved = await uow.events.save_or_resolve_one(evt)
        assert saved.is_ok()
        await uow.commit()

    # Register test processor
    processor_registry.register("evt", TxTestProcessor())

    try:
        # Run the processing use case in a fresh UoW (this will perform TX1 and TX2)
        async with uow_factory() as uow2:
            dto = EnqueuedEventUseCaseOutput(
                id=evt.id,
                name=evt.name,
                state=evt.state,
                external_uuid=evt.external_uuid,
                payload=evt.payload,
                context=evt.context,
            )

            usecase = ProcessEventIdealUseCase(uow2)
            result = await usecase.execute(dto)

            assert result.is_ok()

        # After processing, verify processor observed PROCESSING state (TX1)
        assert any(s == EventState.PROCESSING for s in observed_states), (
            "Processor did not observe PROCESSING state persisted by TX1"
        )

        # Verify final state in DB is COMPLETED (TX2 persisted)
        async with uow_factory() as uow3:
            final_res = await uow3.events.getOne(evt.id)
            assert final_res.is_ok()
            final_evt = final_res.unwrap()
            assert final_evt.state == EventState.COMPLETED

    finally:
        # Cleanup: unregister test processor to avoid side effects for other tests
        try:
            processor_registry._processors.pop("evt", None)  # pragma: no cover - cleanup
        except Exception:
            pass
