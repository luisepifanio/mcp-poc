import sys
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


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
