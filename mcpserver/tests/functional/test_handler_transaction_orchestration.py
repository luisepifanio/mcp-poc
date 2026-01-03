"""
Functional tests for handler-managed transaction orchestration.

FASE 3: Validate that handlers properly manage transactions for use cases.

Tests the new pattern where:
- Handler (infrastructure) opens transaction context with AsyncSQLAlchemyUnitOfWork
- UseCase (core) executes business logic without managing context
- Enables atomic operations: save + publish in single transaction
"""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventState
from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseInput,
    EnqueueEventUseCase,
)
from app.infrastructure.db.unit_of_work import AsyncSQLAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_handler_pattern_transaction_orchestration(
    dbsession: AsyncSession,
) -> None:
    """
    Validate handler-managed transaction orchestration pattern.

    Simulate what the Redis handler does:
    1. Handler opens transaction context with AsyncSQLAlchemyUnitOfWork
    2. Handler instantiates UseCase with UoW
    3. Handler calls UseCase.execute() (no context manager in UseCase)
    4. Handler checks result and decides to publish/ack/nack
    5. Transaction commits atomically on __aexit__

    This pattern ensures:
    - Atomicity: save + publish = single TX
    - Composability: multiple use cases in one TX
    - Testability: use cases don't manage context
    """
    # Simulate handler logic
    event_input = EnqueuedEventUseCaseInput(
        name="OrchestrationTest",
        external_uuid=uuid4(),
        payload={"test": "data"},
        context={"handler": "redis"},
    )

    # This is what the handler does (see app/infrastructure/redis/main.py)
    async with AsyncSQLAlchemyUnitOfWork(dbsession, owns_session=False) as uow:
        # Handler instantiates usecase
        usecase = EnqueueEventUseCase(uow)

        # Handler calls execute (usecase has NO async with)
        result = await usecase.execute(event_input)

        # Handler checks result
        assert result.is_ok()
        saved_event = result.unwrap()

        # If successful, handler would publish here (MEJORA #2)
        # await broker.publish({...})  # Same TX
        # For now, just verify the save worked
        assert saved_event.name == "OrchestrationTest"
        # At this point, transaction is still OPEN
        # It will COMMIT when exiting the async with block

    # Verify persistence after transaction commits
    stmt = select(Event).where(Event.external_uuid == event_input.external_uuid)
    db_result = await dbsession.execute(stmt)
    db_event = db_result.scalar_one_or_none()

    assert db_event is not None
    assert db_event.name == "OrchestrationTest"
    assert db_event.state == EventState.CREATED


@pytest.mark.asyncio
async def test_handler_pattern_rollback_on_error(
    dbsession: AsyncSession,
) -> None:
    """
    Validate that errors in handler context trigger rollback.

    If:
    - Event saves successfully
    - But publish fails (simulated by exception)
    Then:
    - Transaction should rollback
    - Event should NOT be in database
    """
    event_input = EnqueuedEventUseCaseInput(
        name="RollbackTest",
        external_uuid=uuid4(),
        payload={"test": "rollback"},
    )

    # Simulate handler with error after successful save
    try:
        async with AsyncSQLAlchemyUnitOfWork(dbsession, owns_session=False) as uow:
            usecase = EnqueueEventUseCase(uow)
            result = await usecase.execute(event_input)
            assert result.is_ok()

            # Simulate error after save but before publish
            # In production: if broker.publish() fails
            if True:  # Always raise for this test
                raise RuntimeError("Simulated publish failure")
    except RuntimeError:
        pass  # Expected

    # Verify rollback: event should NOT be in database
    stmt = select(Event).where(Event.external_uuid == event_input.external_uuid)
    db_result = await dbsession.execute(stmt)
    db_event = db_result.scalar_one_or_none()

    # After rollback, event should not persist
    assert db_event is None


@pytest.mark.asyncio
async def test_handler_pattern_multiple_use_cases_same_transaction(
    dbsession: AsyncSession,
) -> None:
    """
    Validate that handler can compose multiple use cases in one transaction.

    This is a key benefit of the new pattern:
    - Handler opens ONE transaction
    - Calls UseCase1
    - Calls UseCase2 (if needed)
    - Both are in the same transaction
    - Single commit atomicity
    """
    input1 = EnqueuedEventUseCaseInput(
        name="Event1",
        external_uuid=uuid4(),
        payload={"order": 1},
    )

    input2 = EnqueuedEventUseCaseInput(
        name="Event2",
        external_uuid=uuid4(),
        payload={"order": 2},
    )

    # Handler orchestrates multiple use cases in one TX
    async with AsyncSQLAlchemyUnitOfWork(dbsession, owns_session=False) as uow:
        # UseCase 1
        usecase1 = EnqueueEventUseCase(uow)
        result1 = await usecase1.execute(input1)
        assert result1.is_ok()

        # UseCase 2 (same transaction)
        usecase2 = EnqueueEventUseCase(uow)
        result2 = await usecase2.execute(input2)
        assert result2.is_ok()

    # Both should be persisted after single commit
    stmt = select(Event).where(
        Event.external_uuid.in_([input1.external_uuid, input2.external_uuid])
    )
    db_result = await dbsession.execute(stmt)
    db_events = db_result.scalars().all()

    assert len(db_events) == 2
    assert {e.name for e in db_events} == {"Event1", "Event2"}
