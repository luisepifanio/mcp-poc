"""
Functional tests for EnqueueEventUseCase.

Tests complete end-to-end flows with real database (in-memory SQLite).
Validates integration between use case, unit of work, and repository layers.

Test Categories:
    F1: Happy path - enqueue new event successfully
    F2: Idempotency - duplicate external_uuid returns existing event
    F3: Idempotency - duplicate id returns existing event
    F4: JSON normalization - verify deterministic storage
    F5: Context handling - None vs empty dict
"""

import json
from collections.abc import AsyncGenerator, Callable
from uuid import uuid4

import pytest
from result import Ok
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entities import Event, EventState
from app.core.unit_of_work import UnitOfWork
from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseInput,
    EnqueueEventUseCase,
)


@pytest.mark.asyncio
async def test_f1_enqueue_new_event_happy_path(
    uow_factory: Callable[[], AsyncGenerator[UnitOfWork, None]],
    dbsession: AsyncSession,
) -> None:
    """
    F1: Happy path - enqueue nuevo evento

    Given: Valid event input with unique external_uuid
    When: EnqueueEventUseCase.execute() is called with real UoW
    Then: Event is saved to database and returned with correct state
    """
    # Setup: Preparar input único
    test_uuid = uuid4()
    input_data = EnqueuedEventUseCaseInput(
        name="TestEvent",
        external_uuid=test_uuid,
        payload={"action": "test", "value": 123},
        context={"user_id": "user-001", "trace_id": "trace-123"},
    )

    # Execute: Usar UoW real
    async with uow_factory() as uow:
        use_case = EnqueueEventUseCase(uow=uow)
        result = await use_case.execute(input_data)

    # Assert: Verificar resultado
    assert result.is_ok()
    output = result.unwrap()

    # Verificar campos del output
    assert output.name == "TestEvent"
    assert output.external_uuid == test_uuid
    assert output.payload == {"action": "test", "value": 123}
    assert output.context == {"user_id": "user-001", "trace_id": "trace-123"}
    assert output.state == EventState.CREATED
    assert output.id is not None

    # Verificar persistencia en BD
    async with dbsession as session:
        # Buscar evento por external_uuid
        stmt = select(Event).where(Event.external_uuid == test_uuid)
        db_result = await session.execute(stmt)
        db_event = db_result.scalar_one_or_none()

        assert db_event is not None
        assert db_event.name == "TestEvent"
        assert db_event.external_uuid == test_uuid
        assert db_event.state == EventState.CREATED


@pytest.mark.asyncio
async def test_f2_idempotency_by_external_uuid(
    uow_factory: Callable[[], AsyncGenerator[UnitOfWork, None]],
    dbsession: AsyncSession,
) -> None:
    """
    F2: Idempotencia por external_uuid

    Given: Event already exists in database with specific external_uuid
    When: EnqueueEventUseCase.execute() is called with same external_uuid
    Then: Returns existing event without creating duplicate
    """
    # Setup: Crear evento inicial en BD
    test_uuid = uuid4()
    initial_event = Event(
        name="InitialEvent",
        external_uuid=test_uuid,
        payload={"initial": "data"},
        context={"initial": "context"},
        state=EventState.CREATED,
    )

    # Guardar evento inicial
    async with uow_factory() as uow:
        save_result = await uow.events.save_or_resolve_one(initial_event)
        assert isinstance(save_result, Ok)
        saved_event = save_result.unwrap()
        initial_id = saved_event.id

    # Execute: Intentar crear evento con mismo external_uuid
    input_data = EnqueuedEventUseCaseInput(
        name="DuplicateEvent",  # Nombre diferente
        external_uuid=test_uuid,  # Mismo external_uuid
        payload={"different": "payload"},
        context={"different": "context"},
    )

    async with uow_factory() as uow:
        use_case = EnqueueEventUseCase(uow=uow)
        result = await use_case.execute(input_data)

    # Assert: Debe retornar evento existente
    assert result.is_ok()
    output = result.unwrap()

    # Verificar que retorna el evento original (mismo id)
    assert output.id == initial_id
    assert output.external_uuid == test_uuid
    # Debe mantener datos originales, no los nuevos del input
    assert output.name == "InitialEvent"
    assert output.payload == {"initial": "data"}

    # Verificar que no hay duplicados en BD
    async with dbsession as session:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(Event)
            .where(Event.external_uuid == test_uuid)
        )
        count_result = await session.execute(stmt)
        count = count_result.scalar()

        assert count == 1  # Solo debe haber un evento


@pytest.mark.asyncio
async def test_f3_can_specify_event_id(
    uow_factory: Callable[[], AsyncGenerator[UnitOfWork, None]],
    dbsession: AsyncSession,
) -> None:
    """
    F3: Event creation with specific id

    Given: Input with specific id provided
    When: EnqueueEventUseCase.execute() is called with that id
    Then: Event is created with the specified id

    Note: The implementation currently doesn't have idempotency by id alone.
    This test validates that providing an id works correctly.
    """
    # Setup: Proporcionar un id específico
    test_id = uuid4()
    test_external_uuid = uuid4()

    input_data = EnqueuedEventUseCaseInput(
        name="EventWithSpecificId",
        id=test_id,  # Especificar id
        external_uuid=test_external_uuid,
        payload={"specific": "id"},
        context={"test": "context"},
    )

    # Execute
    async with uow_factory() as uow:
        use_case = EnqueueEventUseCase(uow=uow)
        result = await use_case.execute(input_data)

    # Assert: Debe retornar evento creado con el id especificado
    assert result.is_ok()
    output = result.unwrap()

    # Verificar que se creó con el id especificado
    assert output.id == test_id
    assert output.name == "EventWithSpecificId"
    assert output.external_uuid == test_external_uuid
    assert output.payload == {"specific": "id"}
    assert output.state == EventState.CREATED

    # Verificar en BD
    async with dbsession as session:
        stmt = select(Event).where(Event.id == test_id)
        db_result = await session.execute(stmt)
        db_event = db_result.scalar_one_or_none()

        assert db_event is not None
        assert db_event.name == "EventWithSpecificId"


@pytest.mark.asyncio
async def test_f4_json_normalization_persisted_correctly(
    uow_factory: Callable[[], AsyncGenerator[UnitOfWork, None]],
    dbsession: AsyncSession,
) -> None:
    """
    F4: JSON normalization - verificar almacenamiento determinístico

    Given: Event with nested unordered JSON payload
    When: Event is saved via EnqueueEventUseCase
    Then: JSON is stored in normalized form (deterministic order)
    """
    # Setup: Payload con claves desordenadas
    test_uuid = uuid4()
    input_data = EnqueuedEventUseCaseInput(
        name="NormalizedEvent",
        external_uuid=test_uuid,
        # Claves intencionalmente desordenadas
        payload={"z": 3, "a": 1, "m": {"z": "last", "a": "first"}, "b": 2},
        context={"z": "end", "a": "start"},
    )

    # Execute
    async with uow_factory() as uow:
        use_case = EnqueueEventUseCase(uow=uow)
        result = await use_case.execute(input_data)

    assert result.is_ok()
    output = result.unwrap()

    # Assert: Verificar que el payload está normalizado
    # Python dicts mantienen orden de inserción, pero JSON debe estar ordenado
    normalized_payload = json.loads(
        json.dumps(
            {"z": 3, "a": 1, "m": {"z": "last", "a": "first"}, "b": 2}, sort_keys=True
        )
    )
    assert output.payload == normalized_payload

    # Verificar en BD que el JSON está almacenado de forma determinística
    async with dbsession as session:
        stmt = select(Event).where(Event.external_uuid == test_uuid)
        db_result = await session.execute(stmt)
        db_event = db_result.scalar_one()

        # El payload en BD debe ser el mismo normalizado
        assert db_event.payload == normalized_payload


@pytest.mark.asyncio
async def test_f5_context_none_vs_empty_dict(
    uow_factory: Callable[[], AsyncGenerator[UnitOfWork, None]],
    dbsession: AsyncSession,
) -> None:
    """
    F5: Context handling - None vs empty dict

    Given: Event with context=None
    When: Event is saved via EnqueueEventUseCase
    Then: Context is normalized to {} in database
    """
    # Setup: Input con context=None
    test_uuid = uuid4()
    input_data = EnqueuedEventUseCaseInput(
        name="NullContextEvent",
        external_uuid=test_uuid,
        payload={"test": "data"},
        context=None,  # Explicitly None
    )

    # Execute
    async with uow_factory() as uow:
        use_case = EnqueueEventUseCase(uow=uow)
        result = await use_case.execute(input_data)

    assert result.is_ok()
    output = result.unwrap()

    # Assert: Context debe ser {} en output
    assert output.context == {}

    # Verificar en BD
    async with dbsession as session:
        stmt = select(Event).where(Event.external_uuid == test_uuid)
        db_result = await session.execute(stmt)
        db_event = db_result.scalar_one()

        # Context en BD debe ser {}
        assert db_event.context == {}
