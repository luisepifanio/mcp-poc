from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.processors import RetryConfig

# Fast retry config for tests (56x faster than production defaults)
# Timeline: Attempt 1 (0ms) → Attempt 2 (10ms) → Attempt 3 (20ms) = ~30ms total
# vs Production: ~1700ms
FAST_TEST_RETRY_CONFIG = RetryConfig(
    max_attempts=3,  # Less attempts for speed
    initial_backoff=0.01,  # 10ms (100x faster)
    max_backoff=0.05,  # 50ms (40x faster)
    backoff_multiplier=2.0,  # Same ratio
    fast_retry_count=1,  # Only 1 fast retry
    fast_retry_delay=0.01,  # 10ms (10x faster)
)


@pytest.fixture
def uow_factory():
    """Provide a simple factory that returns an async contextmanager which
    yields an `AsyncSQLAlchwemyUnitOfWork` when given a session.

    This fixture is minimal and purpose-built for unit tests that already
    construct a fake `session` object (MagicMock).
    """
    from app.infrastructure.db.unit_of_work import AsyncSQLAlchemyUnitOfWork

    @asynccontextmanager
    async def _factory(session=None):
        if session is None:
            raise RuntimeError("uow_factory requires a session for unit tests")
        async with AsyncSQLAlchemyUnitOfWork(session) as uow:
            yield uow

    return _factory


@pytest.fixture
def uow_mock() -> MagicMock:
    """
    Proporciona un mock de UnitOfWork completamente configurado para tests unitarios.

    El mock simula:
    - El comportamiento del context manager (async with)
    - Método save_or_resolve() para eventos
    - Métodos de lookup (getOne, get_by_external_uuid, etc.)
    - Comportamiento automático de context manager

    Uso típico:
        @pytest.mark.asyncio
        async def test_enqueue_event(uow_mock):
            uow_mock.events.save_or_resolve = AsyncMock(
                return_value=Ok([event_entity])
            )
            use_case = EnqueueEventUseCase(uow=uow_mock)
            result = await use_case.execute(input_data)
            assert result.is_ok()
    """
    from app.core.unit_of_work import UnitOfWork

    mock = MagicMock(spec=UnitOfWork)

    # Configurar repositorio de eventos con métodos esenciales
    mock.events = MagicMock()
    mock.events.save_or_resolve = AsyncMock()
    mock.events.save_or_resolve_one = AsyncMock()
    mock.events.getOne = AsyncMock()
    mock.events.get_by_external_uuid = AsyncMock()
    mock.events.getMany = AsyncMock()
    # Configurar como async context manager
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)

    return mock
