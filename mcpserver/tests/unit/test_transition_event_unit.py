"""Unit tests for transition_event() function - state machine validation.

Tests cover:
- All valid state transitions
- Invalid state transitions (should be rejected)
- Edge cases (None transitions, duplicate transitions)
- Error detail messages
- EventTransition record creation
"""

from uuid import uuid4

import pytest
from result import Err, Ok

from app.core.entities import Event, EventState, EventTransition
from app.core.usecases.event_usecases import transition_event
from app.errors import ErrorCatalog


class TestTransitionEventValidTransitions:
    """Tests for all valid state transitions."""

    def test_created_to_pending(self):
        """CREATED → PENDING is valid."""
        event = Event(name="test", state=EventState.CREATED)
        result = transition_event(event, EventState.PENDING)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.PENDING
        assert len(event.transitions) == 1
        assert event.transitions[0].from_state == EventState.CREATED
        assert event.transitions[0].to_state == EventState.PENDING

    def test_created_to_failed(self):
        """CREATED → FAILED is valid."""
        event = Event(name="test", state=EventState.CREATED)
        result = transition_event(event, EventState.FAILED)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.FAILED

    def test_pending_to_processing(self):
        """PENDING → PROCESSING is valid (only one transition)."""
        event = Event(name="test", state=EventState.PENDING)
        result = transition_event(event, EventState.PROCESSING)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.PROCESSING

    def test_processing_to_completed(self):
        """PROCESSING → COMPLETED is valid."""
        event = Event(name="test", state=EventState.PROCESSING)
        result = transition_event(event, EventState.COMPLETED)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.COMPLETED

    def test_processing_to_failed(self):
        """PROCESSING → FAILED is valid."""
        event = Event(name="test", state=EventState.PROCESSING)
        result = transition_event(event, EventState.FAILED)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.FAILED

    def test_processing_to_temporal_error(self):
        """PROCESSING → TEMPORAL_ERROR is valid."""
        event = Event(name="test", state=EventState.PROCESSING)
        result = transition_event(event, EventState.TEMPORAL_ERROR)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.TEMPORAL_ERROR

    def test_temporal_error_to_retrying(self):
        """TEMPORAL_ERROR → RETRYING is valid (only one transition)."""
        event = Event(name="test", state=EventState.TEMPORAL_ERROR)
        result = transition_event(event, EventState.RETRYING)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.RETRYING

    def test_retrying_to_completed(self):
        """RETRYING → COMPLETED is valid."""
        event = Event(name="test", state=EventState.RETRYING)
        result = transition_event(event, EventState.COMPLETED)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.COMPLETED

    def test_retrying_to_exhausted(self):
        """RETRYING → EXHAUSTED is valid."""
        event = Event(name="test", state=EventState.RETRYING)
        result = transition_event(event, EventState.EXHAUSTED)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.EXHAUSTED

    def test_retrying_to_temporal_error(self):
        """RETRYING → TEMPORAL_ERROR is valid."""
        event = Event(name="test", state=EventState.RETRYING)
        result = transition_event(event, EventState.TEMPORAL_ERROR)

        assert result.is_ok()
        event = result.unwrap()
        assert event.state == EventState.TEMPORAL_ERROR


class TestTransitionEventInvalidTransitions:
    """Tests for invalid state transitions (should be rejected)."""

    def test_created_to_completed_invalid(self):
        """CREATED → COMPLETED is invalid."""
        event = Event(name="test", state=EventState.CREATED)
        result = transition_event(event, EventState.COMPLETED)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.error == ErrorCatalog.VALIDATION_FAILED.value
        # Error uses .value (lowercase)
        assert EventState.CREATED.value in error.detail
        assert EventState.COMPLETED.value in error.detail

    def test_created_to_processing_invalid(self):
        """CREATED → PROCESSING is invalid."""
        event = Event(name="test", state=EventState.CREATED)
        result = transition_event(event, EventState.PROCESSING)

        assert result.is_err()

    def test_pending_to_completed_invalid(self):
        """PENDING → COMPLETED is invalid."""
        event = Event(name="test", state=EventState.PENDING)
        result = transition_event(event, EventState.COMPLETED)

        assert result.is_err()

    def test_pending_to_failed_invalid(self):
        """PENDING → FAILED is invalid."""
        event = Event(name="test", state=EventState.PENDING)
        result = transition_event(event, EventState.FAILED)

        assert result.is_err()

    def test_completed_to_any_invalid(self):
        """COMPLETED has no valid transitions."""
        event = Event(name="test", state=EventState.COMPLETED)
        result = transition_event(event, EventState.RETRYING)

        assert result.is_err()

    def test_failed_to_any_invalid(self):
        """FAILED has no valid transitions."""
        event = Event(name="test", state=EventState.FAILED)
        result = transition_event(event, EventState.RETRYING)

        assert result.is_err()

    def test_exhausted_to_any_invalid(self):
        """EXHAUSTED has no valid transitions."""
        event = Event(name="test", state=EventState.EXHAUSTED)
        result = transition_event(event, EventState.RETRYING)

        assert result.is_err()

    def test_processing_to_pending_invalid(self):
        """PROCESSING → PENDING is invalid (backward transition)."""
        event = Event(name="test", state=EventState.PROCESSING)
        result = transition_event(event, EventState.PENDING)

        assert result.is_err()


class TestTransitionEventEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_transition_appends_to_existing_transitions(self):
        """Multiple transitions should accumulate."""
        event = Event(name="test", state=EventState.CREATED)

        # First transition
        result1 = transition_event(event, EventState.PENDING)
        assert result1.is_ok()
        event = result1.unwrap()
        assert len(event.transitions) == 1

        # Second transition
        result2 = transition_event(event, EventState.PROCESSING)
        assert result2.is_ok()
        event = result2.unwrap()
        assert len(event.transitions) == 2
        assert event.transitions[0].to_state == EventState.PENDING
        assert event.transitions[1].to_state == EventState.PROCESSING

    def test_transition_records_event_id(self):
        """EventTransition should record the event_id."""
        event_id = uuid4()
        event = Event(name="test", state=EventState.CREATED, id=event_id)

        result = transition_event(event, EventState.PENDING)

        assert result.is_ok()
        event = result.unwrap()
        assert event.transitions[0].event_id == event_id

    def test_transition_records_states(self):
        """EventTransition should record from_state and to_state."""
        event = Event(name="test", state=EventState.CREATED)

        result = transition_event(event, EventState.PENDING)

        assert result.is_ok()
        event = result.unwrap()
        transition = event.transitions[0]
        assert transition.from_state == EventState.CREATED
        assert transition.to_state == EventState.PENDING

    def test_state_machine_full_happy_path(self):
        """Test a complete valid flow through the state machine."""
        event = Event(name="test", state=EventState.CREATED)

        # CREATED → PENDING
        event = transition_event(event, EventState.PENDING).unwrap()
        assert event.state == EventState.PENDING
        assert len(event.transitions) == 1

        # PENDING → PROCESSING
        event = transition_event(event, EventState.PROCESSING).unwrap()
        assert event.state == EventState.PROCESSING
        assert len(event.transitions) == 2

        # PROCESSING → COMPLETED
        event = transition_event(event, EventState.COMPLETED).unwrap()
        assert event.state == EventState.COMPLETED
        assert len(event.transitions) == 3

        # Verify final state
        assert event.transitions[-1].to_state == EventState.COMPLETED

    def test_state_machine_with_error_recovery(self):
        """Test error recovery path: PROCESSING → TEMPORAL_ERROR → RETRYING."""
        event = Event(name="test", state=EventState.PROCESSING)

        # PROCESSING → TEMPORAL_ERROR
        event = transition_event(event, EventState.TEMPORAL_ERROR).unwrap()
        assert event.state == EventState.TEMPORAL_ERROR

        # TEMPORAL_ERROR → RETRYING
        event = transition_event(event, EventState.RETRYING).unwrap()
        assert event.state == EventState.RETRYING
        assert len(event.transitions) == 2

    def test_state_machine_exhausted_path(self):
        """Test exhaustion path: PROCESSING → TEMPORAL_ERROR → RETRYING → EXHAUSTED."""
        event = Event(name="test", state=EventState.PROCESSING)

        event = transition_event(event, EventState.TEMPORAL_ERROR).unwrap()
        event = transition_event(event, EventState.RETRYING).unwrap()
        event = transition_event(event, EventState.EXHAUSTED).unwrap()

        assert event.state == EventState.EXHAUSTED
        assert len(event.transitions) == 3


class TestTransitionEventErrorMessages:
    """Tests for error message clarity."""

    def test_error_detail_includes_both_states(self):
        """Error message should include both from and to states."""
        event = Event(name="test", state=EventState.COMPLETED)
        result = transition_event(event, EventState.PENDING)

        assert result.is_err()
        error = result.unwrap_err()
        # Error format: "( {from_state.value} , {to_state.value} ) is not a valid transition"
        assert EventState.COMPLETED.value in error.detail
        assert EventState.PENDING.value in error.detail

    def test_error_type_is_validation_failed(self):
        """Error type should be VALIDATION_FAILED."""
        event = Event(name="test", state=EventState.FAILED)
        result = transition_event(event, EventState.CREATED)

        assert result.is_err()
        error = result.unwrap_err()
        assert error.error == ErrorCatalog.VALIDATION_FAILED.value
