"""
Functional tests for EnqueueEventUseCase concurrency scenarios.

Tests race conditions and idempotence under concurrent execution.
Validates that multiple simultaneous requests for the same event
result in a single, consistent record in the database.

Test Categories:
    C1: 2 requests con mismo external_uuid (idempotence by external UUID)
    C2: 5 requests con mismo id (idempotence by internal UUID)
"""

import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventState
from app.core.unit_of_work import UnitOfWork
from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseInput,
    EnqueueEventUseCase,
)


@pytest.mark.asyncio
async def test_c1_concurrent_same_external_uuid(
    uow_factory: AsyncGenerator[UnitOfWork, None],
    dbsession: AsyncSession,
) -> None:
    """
    C1: Concurrent requests with same external_uuid (idempotence test)

    Given: 2 simultaneous requests with the same external_uuid
    When: EnqueueEventUseCase.execute() is called concurrently (asyncio.gather)
    Then:
        - Both requests complete successfully
        - Both return the SAME event (same id, external_uuid)
        - Database contains only 1 Event record
        - No duplicates or conflicts

    Race condition scenario: Both requests hit save_or_resolve_one at nearly
    the same time. The first transaction should succeed and lock. The second
    should detect the existing external_uuid and return the same event.
    """
    # Arrange: Create a fixed external_uuid to force collision
    shared_external_uuid = uuid4()

    async def make_request() -> dict:
        """Execute one EnqueueEventUseCase request."""
        async with uow_factory() as uow:
            use_case = EnqueueEventUseCase(uow=uow)
            input_data = EnqueuedEventUseCaseInput(
                name="ConcurrentEvent",
                payload={"key": "value"},
                external_uuid=shared_external_uuid,
            )
            result = await use_case.execute(input_data)
            assert result.is_ok(), f"Use case failed: {result.unwrap_err()}"
            output = result.unwrap()
            return {
                "id": output.id,
                "external_uuid": output.external_uuid,
                "name": output.name,
                "state": output.state,
            }

    # Act: Execute 2 requests concurrently with same external_uuid
    results = await asyncio.gather(make_request(), make_request())

    # Assert: Both requests returned the same event
    result1, result2 = results
    assert result1["external_uuid"] == result2["external_uuid"]
    assert result1["id"] == result2["id"], "Both requests should return the same event id"
    assert result1["name"] == result2["name"]
    assert result1["state"] == EventState.CREATED

    # Assert: Database contains only 1 Event (no duplicates)
    stmt = select(Event).where(Event.external_uuid == shared_external_uuid)
    db_events = await dbsession.execute(stmt)
    events = db_events.scalars().all()
    assert len(events) == 1, (
        f"Expected 1 event in DB for external_uuid={shared_external_uuid}, "
        f"found {len(events)}"
    )

    # Assert: The event in DB matches the returned outputs
    db_event = events[0]
    assert db_event.id == result1["id"]
    assert db_event.external_uuid == shared_external_uuid
    assert db_event.state == EventState.CREATED


@pytest.mark.asyncio
async def test_c2_concurrent_same_internal_id(
    uow_factory: AsyncGenerator[UnitOfWork, None],
    dbsession: AsyncSession,
) -> None:
    """
    C2: Concurrent requests with same id (idempotence by internal UUID)

    Given: 5 simultaneous requests with the same id (internal UUID)
    When: EnqueueEventUseCase.execute() is called concurrently (asyncio.gather)
    Then:
        - All 5 requests complete successfully
        - All return the SAME event (same id)
        - Database contains only 1 Event record with that id
        - No race condition conflicts

    Race condition scenario: User explicitly specifies the same id in all 5
    requests. First request creates the event. Remaining 4 should detect
    the existing id and return the same event (save_or_resolve idempotence).
    """
    # Arrange: Create a fixed internal id (UUID) to force collision
    shared_id = uuid4()

    async def make_request(request_num: int) -> dict:
        """Execute one EnqueueEventUseCase request."""
        async with uow_factory() as uow:
            use_case = EnqueueEventUseCase(uow=uow)
            input_data = EnqueuedEventUseCaseInput(
                name=f"ConcurrentEvent-{request_num}",
                payload={"request": request_num},
                id=shared_id,  # Same id for all requests
                external_uuid=uuid4(),  # Different external_uuid per request
            )
            result = await use_case.execute(input_data)
            assert result.is_ok(), f"Use case failed: {result.unwrap_err()}"
            output = result.unwrap()
            return {
                "id": output.id,
                "external_uuid": output.external_uuid,
                "name": output.name,
                "state": output.state,
                "request_num": request_num,
            }

    # Act: Execute 5 concurrent requests with same id
    results = await asyncio.gather(
        make_request(1),
        make_request(2),
        make_request(3),
        make_request(4),
        make_request(5),
    )

    # Assert: All requests returned the same id
    all_ids = [r["id"] for r in results]
    assert all(id == shared_id for id in all_ids), (
        f"All requests should return the same id={shared_id}. Got: {all_ids}"
    )

    # Assert: All requests have the same state
    all_states = [r["state"] for r in results]
    assert all(s == EventState.CREATED for s in all_states), (
        f"All events should be in CREATED state. Got: {all_states}"
    )

    # Assert: Database contains only 1 Event with the shared id
    stmt = select(Event).where(Event.id == shared_id)
    db_events = await dbsession.execute(stmt)
    events = db_events.scalars().all()
    assert len(events) == 1, (
        f"Expected 1 event in DB with id={shared_id}, found {len(events)}"
    )

    # Assert: The event in DB matches the returned outputs
    db_event = events[0]
    assert db_event.id == shared_id
    assert db_event.state == EventState.CREATED

    # Assert: All requests return the same external_uuid (the winner's)
    # This is correct behavior: when ID conflicts, the existing event is returned
    # with its original external_uuid (the first one that was saved)
    external_uuids = [r["external_uuid"] for r in results]
    unique_external_uuids = set(external_uuids)
    assert len(unique_external_uuids) == 1, (
        f"When same ID is used, all requests should return the same event "
        f"with the same external_uuid. Expected 1 unique external_uuid, "
        f"but got {len(unique_external_uuids)}. "
        f"Got: {external_uuids}"
    )

    # Assert: The returned external_uuid is the one from the first successful request
    assert external_uuids[0] == db_event.external_uuid, (
        "Returned external_uuid should match the DB record's external_uuid"
    )


@pytest.mark.asyncio
async def test_c3_concurrent_mixed_id_and_external_uuid(
    uow_factory: AsyncGenerator[UnitOfWork, None],
    dbsession: AsyncSession,
) -> None:
    """
    C3: Mixed concurrency: same external_uuid, different IDs.

    Escenario mixto: un request fuerza un ID explícito y otro usa un ID
    distinto, pero ambos comparten external_uuid. Deben resolver al MISMO
    evento, demostrando idempotencia incluso cuando el cliente propone
    IDs diferentes pero el external_uuid ya existe.
    """

    shared_external_uuid = uuid4()
    explicit_id = uuid4()

    async def request_with_explicit_id() -> dict:
        """Colisiona con external_uuid compartido pero fuerza un ID explícito."""
        async with uow_factory() as uow:
            use_case = EnqueueEventUseCase(uow=uow)
            input_data = EnqueuedEventUseCaseInput(
                name="Mixed-Explicit-ID",
                payload={"via": "explicit-id"},
                id=explicit_id,
                external_uuid=shared_external_uuid,
            )
            result = await use_case.execute(input_data)
            assert result.is_ok(), f"Use case failed: {result.unwrap_err()}"
            output = result.unwrap()
            return {
                "id": output.id,
                "external_uuid": output.external_uuid,
                "name": output.name,
                "state": output.state,
            }

    async def request_with_different_id() -> dict:
        """Colisiona por el mismo external_uuid pero propone un ID distinto."""
        async with uow_factory() as uow:
            use_case = EnqueueEventUseCase(uow=uow)
            input_data = EnqueuedEventUseCaseInput(
                name="Mixed-Different-ID",
                payload={"via": "different-id"},
                id=uuid4(),  # Different id, same external_uuid
                external_uuid=shared_external_uuid,
            )
            result = await use_case.execute(input_data)
            assert result.is_ok(), f"Use case failed: {result.unwrap_err()}"
            output = result.unwrap()
            return {
                "id": output.id,
                "external_uuid": output.external_uuid,
                "name": output.name,
                "state": output.state,
            }

    # Act: run both requests concurrently
    results = await asyncio.gather(
        request_with_explicit_id(),
        request_with_different_id(),
    )

    # Assert: both resolve to the SAME event (idempotent on external_uuid)
    ids = {r["id"] for r in results}
    external_uuids = {r["external_uuid"] for r in results}

    assert len(ids) == 1, f"Expected a single event id, got {ids}"
    assert external_uuids == {shared_external_uuid}, (
        f"Expected external_uuid={shared_external_uuid}, got {external_uuids}"
    )

    # Assert: DB contains only one event for that external_uuid
    stmt = select(Event).where(Event.external_uuid == shared_external_uuid)
    db_events = await dbsession.execute(stmt)
    events = db_events.scalars().all()
    assert len(events) == 1, (
        f"Expected 1 event for external_uuid={shared_external_uuid}, found {len(events)}"
    )

    db_event = events[0]
    assert db_event.id in ids
    assert db_event.state == EventState.CREATED
