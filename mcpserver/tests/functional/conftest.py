import logging
import os
from collections.abc import AsyncGenerator, Callable
from typing import Any

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from fastapi.testclient import TestClient as FastApiTestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.core.logconfig import setup_logging

# Get a logger for this module
logger = logging.getLogger(__name__)


# @pytest.fixture(autouse=True, scope="session")
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_env() -> AsyncGenerator[None, None]:
    # Configura el entorno de prueba
    os.environ["ENV"] = "test"
    load_dotenv(dotenv_path="test.env")
    setup_logging()
    logger.info("🟢 Test environment ready")

    # Prompt environment values..
    # for key, value in os.environ.items():
    #    logger.info(f"ENV {key}={value}")
    # Clear any cached settings from earlier unit tests so functional
    # test env takes effect when we call `getAppSettings()`.
    from app.core import settings as settings_mod

    # Clear cached settings and obtain a fresh instance (use new reload API)
    if hasattr(settings_mod, "getAppSettings"):
        settings = settings_mod.getAppSettings(reload=True)
    else:
        # Fallback: direct manipulation of internal cache
        settings_mod._config = None
        settings = settings_mod.getAppSettings()

    # Importamos inline para cambiar las variables de entorno primero
    from app.infrastructure.db.connection import async_engine

    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        yield
        await conn.run_sync(SQLModel.metadata.drop_all)
        await async_engine.dispose()

    # Remove file on settings.database_url if it is a sqlite file
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.replace("sqlite:///", "")
        if os.path.exists(db_path):
            logger.warning(f"Removing test database file at {db_path}")
            os.remove(db_path)


@pytest.fixture(autouse=True, scope="function")
def value_inject() -> str:
    return "injected_value"


@pytest.fixture(autouse=True, scope="function")
def http_client() -> FastApiTestClient:
    from app.infrastructure.api.main import app

    return FastApiTestClient(app)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # host, port = "127.0.0.1", "9000"
    from app.infrastructure.api.main import app

    async with AsyncClient(
        transport=ASGITransport(
            app=app,
            # client=(host, port)
        ),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_session_local() -> Any:
    """Provides the `AsyncSession` factory (`async_sessionmaker`) used by tests.

    Returns the value produced by `app.infrastructure.db.connection.get_session_local()`
    so tests only depend on the fixture name and not the import call.
    """
    from app.infrastructure.db.connection import get_session_local

    return await get_session_local()


@pytest_asyncio.fixture(scope="function")
async def uow_factory(async_session_local: Any) -> Callable[..., Any]:
    """Provide a small async contextmanager factory for `UnitOfWork` instances.

    Usage in tests:

        async with uow_factory() as uow:
            # use uow

    Or, to bind a specific session (e.g. when coordinating multiple actions
    within the same DB session):

        async with AsyncSessionLocal() as session:
            async with uow_factory(session) as uow:
                # use uow bound to `session`

    This helper reduces boilerplate in tests and centralizes construction
    of `AsyncSQLAlchwemyUnitOfWork`.
    """
    from contextlib import asynccontextmanager

    from app.infrastructure.db.unit_of_work import AsyncSQLAlchemyUnitOfWork

    AsyncSessionLocal = async_session_local

    @asynccontextmanager
    async def _uow(session: AsyncSession | None = None) -> AsyncGenerator[Any, None]:
        if session is None:
            async with AsyncSessionLocal() as session:
                async with AsyncSQLAlchemyUnitOfWork(session) as uow:
                    yield uow
        else:
            async with AsyncSQLAlchemyUnitOfWork(session) as uow:
                yield uow

    return _uow


@pytest_asyncio.fixture(scope="function")
async def dbsession() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh `AsyncSession` for each test function.

    Previous implementation produced a session-scoped `dbsession`, which could
    leak transactional state across tests. Creating a new session per test
    reduces flakiness and matches other fixtures that expect independent
    sessions.
    """
    from app.infrastructure.db.connection import get_session_local

    AsyncSessionLocal = await get_session_local()

    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True, scope="session")
def fix_session():
    # logger.info("INFO")
    # logger.debug("DEBUG")
    # logger.warning("WARNING")
    # logger.error("ERROR")
    # logger.critical("CRITICAL")

    # logger.debug("Session setup")
    yield
    # logger.debug("Session teardown")


## Example fixtures
@pytest.fixture(autouse=True, scope="module")
def fix_module():
    # logger.debug("Module setup")
    yield
    # logger.debug("Module teardown")


@pytest.fixture(autouse=True, scope="function")
def fix_function():
    # logger.debug("Function setup")
    yield
    # logger.debug(" Function teardown")
