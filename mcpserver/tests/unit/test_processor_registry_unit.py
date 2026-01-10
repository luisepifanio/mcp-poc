"""Unit tests for ProcessorRegistry."""

import pytest

from app.core.processor_registry import (
    NoOpProcessor,
    ProcessorRegistry,
    processor_registry,
)
from app.core.processors import ErrorType


def test_processor_registry_register_and_get():
    """Test registering and retrieving a processor."""
    registry = ProcessorRegistry()
    processor = NoOpProcessor()

    registry.register("test_event", processor)
    retrieved = registry.get("test_event")

    assert retrieved is processor


def test_processor_registry_returns_noop_for_unregistered():
    """Test that unregistered events return NoOpProcessor."""
    registry = ProcessorRegistry()

    processor = registry.get("unknown_event")

    assert isinstance(processor, NoOpProcessor)


def test_processor_registry_has_checks_explicit_registration():
    """Test has() method checks explicit registration only."""
    registry = ProcessorRegistry()

    # Unregistered event - has() should return False even though get() returns NoOp
    assert registry.has("unknown_event") is False

    # Register explicit processor
    registry.register("test_event", NoOpProcessor())
    assert registry.has("test_event") is True


def test_processor_registry_list_registered():
    """Test listing registered processors."""
    registry = ProcessorRegistry()

    registry.register("event1", NoOpProcessor())
    registry.register("event2", NoOpProcessor())

    registered = registry.list_registered()

    assert "event1" in registered
    assert "event2" in registered
    assert len(registered) == 2


def test_noop_processor_raises_error_on_process():
    """Test NoOpProcessor raises ValueError when processing."""
    import asyncio
    from unittest.mock import MagicMock

    processor = NoOpProcessor()
    event = MagicMock()
    event.name = "unknown_event"
    event.id = "test-id"
    event.payload = {"test": "data"}

    with pytest.raises(ValueError, match="No processor registered"):
        asyncio.run(processor.process(event))


def test_noop_processor_retry_config_no_retries():
    """Test NoOpProcessor has no retries."""
    processor = NoOpProcessor()
    config = processor.get_retry_config()

    assert config.max_attempts == 1


def test_noop_processor_classifies_as_permanent():
    """Test NoOpProcessor classifies errors as PERMANENT."""
    processor = NoOpProcessor()

    error_type = processor.classify_error(ValueError("test"))

    assert error_type == ErrorType.PERMANENT


def test_global_processor_registry_exists():
    """Test global processor_registry instance exists."""
    assert processor_registry is not None
    assert isinstance(processor_registry, ProcessorRegistry)


def test_setup_processors_registers_sync_and_async_processors():
    """setup_processors should register all processors when broker and uow provided."""
    from unittest.mock import MagicMock, patch

    broker = MagicMock()
    uow = MagicMock()

    with (
        patch("app.core.processor_registry.processor_registry.register") as mock_register,
        patch(
            "app.infrastructure.processors.sync_processors.ApiCallProcessor",
            autospec=True,
        ),
        patch(
            "app.infrastructure.processors.sync_processors.GrpcProcessor", autospec=True
        ),
        patch(
            "app.infrastructure.processors.sync_processors.LocalUseCaseProcessor",
            autospec=True,
        ),
        patch(
            "app.infrastructure.processors.long_running_processor.ScrapingProcessor",
            autospec=True,
        ),
        patch(
            "app.infrastructure.processors.long_running_processor.MlInferenceProcessor",
            autospec=True,
        ),
        patch(
            "app.infrastructure.processors.long_running_processor.BatchExportProcessor",
            autospec=True,
        ),
    ):
        from app.core.processor_registry import setup_processors

        setup_processors(broker=broker, uow=uow)

        registered_names = [call.args[0] for call in mock_register.call_args_list]
        assert "api_call" in registered_names
        assert "grpc_call" in registered_names
        assert "local_usecase" in registered_names
        assert "scraping_task" in registered_names
        assert "ml_inference" in registered_names
        assert "batch_export" in registered_names


def test_setup_processors_skips_when_no_broker_or_uow():
    """setup_processors should only register sync processors without broker/uow."""
    from unittest.mock import patch

    with (
        patch("app.core.processor_registry.processor_registry.register") as mock_register,
        patch(
            "app.infrastructure.processors.sync_processors.ApiCallProcessor",
            autospec=True,
        ),
        patch(
            "app.infrastructure.processors.sync_processors.GrpcProcessor", autospec=True
        ),
        patch(
            "app.infrastructure.processors.sync_processors.LocalUseCaseProcessor",
            autospec=True,
        ),
    ):
        from app.core.processor_registry import setup_processors

        setup_processors(broker=None, uow=None)

        registered_names = [call.args[0] for call in mock_register.call_args_list]
        assert "api_call" in registered_names
        assert "grpc_call" in registered_names
        assert "local_usecase" not in registered_names
        assert "scraping_task" not in registered_names
        assert "ml_inference" not in registered_names
        assert "batch_export" not in registered_names
