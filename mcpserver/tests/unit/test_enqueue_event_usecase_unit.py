"""
Unit tests for EnqueueEventUseCase.

Tests the use case logic in isolation using dependency injection with mocked
UnitOfWork. No database access.

Test Categories:
    U1: Valid input, new event -> Ok(output)
    U2: Invalid Pydantic input -> caught during construction
    U3: Invalid state (not CREATED) -> Err(VALIDATION_FAILED)
    U4: JSON normalization -> deterministic sort_keys=True
    U5: Event creation and normalization
"""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from result import Ok

from app.core.entities import Event, EventState
from app.core.usecases.event_usecases import (
    EnqueuedEventUseCaseInput,
    EnqueuedEventUseCaseOutput,
    EnqueueEventUseCase,
)
from app.errors import ErrorCatalog


@pytest.mark.asyncio
async def test_u1_valid_input_new_event(uow_mock: MagicMock) -> None:
    """
    U1: Input válido, nuevo evento -> Ok(output)

    Given: Valid input with name, payload, context
    When: EnqueueEventUseCase.execute() is called
    Then: Returns Ok(EnqueuedEventUseCaseOutput)
    """
    # Setup: Mock UoW returns Ok with new event
    test_event = Event(
        id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        name="TestEvent",
        external_uuid=UUID("550e8400-e29b-41d4-a716-446655440002"),
        payload={"key": "value"},
        context={"trace_id": "123"},
        state=EventState.CREATED,
    )

    uow_mock.events.save_or_resolve_one = AsyncMock(return_value=Ok(test_event))

    # Execute
    use_case = EnqueueEventUseCase(uow=uow_mock)
    input_data = EnqueuedEventUseCaseInput(
        name="TestEvent",
        payload={"key": "value"},
        context={"trace_id": "123"},
    )
    result = await use_case.execute(input_data)

    # Assert
    assert result.is_ok()
    output = result.unwrap()
    assert isinstance(output, EnqueuedEventUseCaseOutput)
    assert output.name == "TestEvent"
    assert output.payload == {"key": "value"}
    assert output.context == {"trace_id": "123"}

    # Verify mock was called
    uow_mock.events.save_or_resolve_one.assert_called_once()


@pytest.mark.asyncio
async def test_u2_invalid_pydantic_input_missing_name(
    uow_mock: MagicMock,
) -> None:
    """
    U2: Input with missing required name

    Given: Missing required field 'name'
    When: EnqueuedEventUseCaseInput is constructed
    Then: Pydantic raises ValidationError at construction
    """
    with pytest.raises(ValidationError) as exc_info:
        EnqueuedEventUseCaseInput(payload={"key": "value"})  # type: ignore
    
    # Verify error message contains field information
    assert "name" in str(exc_info.value).lower()
    assert "required" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_u2_invalid_pydantic_input_oversized_name(
    uow_mock: MagicMock,
) -> None:
    """
    U2: Input with name exceeding max_length

    Given: Input with name exceeding max_length (100)
    When: EnqueuedEventUseCaseInput is constructed
    Then: Pydantic raises ValidationError
    """
    with pytest.raises(ValidationError) as exc_info:
        EnqueuedEventUseCaseInput(
            name="x" * 101,  # Exceeds max_length=100
            payload={"key": "value"},
        )
    
    # Verify error message contains string length validation
    assert "string_too_long" in str(exc_info.value).lower() or "at most 100" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_u3_invalid_state_not_created(uow_mock: MagicMock) -> None:
    """
    U3: Estado inválido (no CREATED) -> Err(VALIDATION_FAILED)

    Given: Input with state=PENDING (not allowed)
    When: EnqueueEventUseCase.execute() is called
    Then: Returns Err(VALIDATION_FAILED) with detail about invalid state
    """
    # Setup
    use_case = EnqueueEventUseCase(uow=uow_mock)
    input_data = EnqueuedEventUseCaseInput(
        name="TestEvent",
        payload={"key": "value"},
        state=EventState.PENDING,  # Invalid: only CREATED or None
    )

    # Execute
    result = await use_case.execute(input_data)

    # Assert
    assert result.is_err()
    error = result.unwrap_err()
    assert error.error == ErrorCatalog.VALIDATION_FAILED.value
    assert "PENDING" in error.detail
    assert "Invalid initial state" in error.detail

    # Verify mock was NOT called (validation failed before UoW)
    uow_mock.events.save_or_resolve_one.assert_not_called()


@pytest.mark.asyncio
async def test_u3_invalid_state_processing(uow_mock: MagicMock) -> None:
    """
    U3: Estado inválido PROCESSING -> Err(VALIDATION_FAILED)

    Given: Input with state=PROCESSING (not allowed)
    When: EnqueueEventUseCase.execute() is called
    Then: Returns Err(VALIDATION_FAILED) with specific message
    """
    # Setup
    use_case = EnqueueEventUseCase(uow=uow_mock)
    input_data = EnqueuedEventUseCaseInput(
        name="TestEvent",
        payload={"key": "value"},
        state=EventState.PROCESSING,
    )

    # Execute
    result = await use_case.execute(input_data)

    # Assert: Forzar validación específica del mensaje del use case
    assert result.is_err()
    error = result.unwrap_err()
    assert error.error == ErrorCatalog.VALIDATION_FAILED.value
    # Validar mensaje específico que use case debe generar
    assert "PROCESSING" in error.detail
    assert "Invalid initial state" in error.detail
    assert "Only CREATED or None are allowed" in error.detail
    
    # Verificar que el mock NO fue llamado (validación antes de UoW)
    uow_mock.events.save_or_resolve_one.assert_not_called()


@pytest.mark.asyncio
async def test_u4_json_normalization_nested_dict(
    uow_mock: MagicMock,
) -> None:
    """
    U4: JSON normalization -> deterministic sort_keys=True

    Given: Input with nested dicts in different orders
    When: EnqueueEventUseCase normalizes JSON
    Then: JSON is deterministically ordered (sort_keys=True)
    """
    # Setup: Create event with normalized payload
    test_event = Event(
        id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        name="TestEvent",
        external_uuid=UUID("550e8400-e29b-41d4-a716-446655440002"),
        # Payload should be normalized (sorted keys)
        payload={"a": 2, "m": {"a": "first", "z": "last"}, "z": 1},
        context={"a": "first", "z": "last"},
        state=EventState.CREATED,
    )

    uow_mock.events.save_or_resolve_one = AsyncMock(return_value=Ok(test_event))

    # Execute with unsorted payload
    use_case = EnqueueEventUseCase(uow=uow_mock)
    input_data = EnqueuedEventUseCaseInput(
        name="TestEvent",
        # Provide unsorted (Python dict iteration order doesn't guarantee)
        payload={"z": 1, "a": 2, "m": {"z": "last", "a": "first"}},
        context={"z": "last", "a": "first"},
    )
    result = await use_case.execute(input_data)

    # Assert
    assert result.is_ok()

    # Verify that save_or_resolve_one was called
    call_args = uow_mock.events.save_or_resolve_one.call_args
    assert call_args is not None
    saved_event = call_args[0][0]  # First positional argument (the event)

    # Verify payload was normalized by checking it equals json-loads-dumps-sorted
    expected_payload = json.loads(
        json.dumps(
            {"z": 1, "a": 2, "m": {"z": "last", "a": "first"}},
            sort_keys=True,
        )
    )
    assert saved_event.payload == expected_payload


@pytest.mark.asyncio
async def test_u4_json_normalization_none_context(
    uow_mock: MagicMock,
) -> None:
    """
    U4: JSON normalization with None context -> normalized to empty dict

    Given: Input with context=None
    When: EnqueueEventUseCase normalizes JSON
    Then: Context is set to {} (empty dict)
    """
    # Setup
    test_event = Event(
        id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        name="TestEvent",
        external_uuid=UUID("550e8400-e29b-41d4-a716-446655440002"),
        payload={"key": "value"},
        context={},
        state=EventState.CREATED,
    )

    uow_mock.events.save_or_resolve_one = AsyncMock(return_value=Ok(test_event))

    # Execute with context=None
    use_case = EnqueueEventUseCase(uow=uow_mock)
    input_data = EnqueuedEventUseCaseInput(
        name="TestEvent",
        payload={"key": "value"},
        context=None,
    )
    result = await use_case.execute(input_data)

    # Assert
    assert result.is_ok()

    # Verify context was normalized to {}
    call_args = uow_mock.events.save_or_resolve_one.call_args
    assert call_args is not None
    saved_event = call_args[0][0]
    assert saved_event.context == {}


@pytest.mark.asyncio
async def test_u5_event_defaults_to_created_state(
    uow_mock: MagicMock,
) -> None:
    """
    U5: Event creation with state defaulting to CREATED

    Given: Input with state=None (default)
    When: EnqueueEventUseCase.execute() is called
    Then: Event is created with state CREATED
    """

    # Setup
    def save_or_resolve_one_side_effect(event):
        # Verify event has CREATED state
        assert event.state == EventState.CREATED
        return Ok(event)

    uow_mock.events.save_or_resolve_one = AsyncMock(
        side_effect=save_or_resolve_one_side_effect
    )

    # Execute with state=None
    use_case = EnqueueEventUseCase(uow=uow_mock)
    input_data = EnqueuedEventUseCaseInput(
        name="TestEvent",
        payload={"key": "value"},
        state=None,  # Should default to CREATED
    )
    result = await use_case.execute(input_data)

    # Assert
    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.CREATED


@pytest.mark.asyncio
async def test_u5_output_validation_completes_successfully(
    uow_mock: MagicMock,
) -> None:
    """
    U5: Output validation -> Pydantic validates before returning

    Given: Event saved successfully with all fields
    When: EnqueueEventUseCase validates output with Pydantic
    Then: Returns Ok(EnqueuedEventUseCaseOutput) with all fields valid
    """
    # Setup: Event with just required fields for output
    test_event = Event(
        id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        name="TestEvent",
        external_uuid=UUID("550e8400-e29b-41d4-a716-446655440002"),
        payload={"key": "value", "nested": {"inner": "data"}},
        context={"trace_id": "abc123", "user_id": "user-001"},
        state=EventState.CREATED,
    )

    uow_mock.events.save_or_resolve_one = AsyncMock(return_value=Ok(test_event))

    # Execute
    use_case = EnqueueEventUseCase(uow=uow_mock)
    input_data = EnqueuedEventUseCaseInput(
        name="TestEvent",
        payload={"key": "value", "nested": {"inner": "data"}},
        context={"trace_id": "abc123", "user_id": "user-001"},
    )
    result = await use_case.execute(input_data)

    # Assert
    assert result.is_ok()
    output = result.unwrap()

    # Verify all fields are present and correct
    assert output.id == UUID("550e8400-e29b-41d4-a716-446655440001")
    assert output.name == "TestEvent"
    assert output.state == EventState.CREATED
    assert output.external_uuid == UUID("550e8400-e29b-41d4-a716-446655440002")
    assert output.payload == {"key": "value", "nested": {"inner": "data"}}
    assert output.context == {"trace_id": "abc123", "user_id": "user-001"}
