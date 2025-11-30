import logging
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from fastapi.testclient import TestClient as FastApiTestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.core.logconfig import setup_logging
from app.core.settings import getAppSettings

# Get a logger for this module
logger = logging.getLogger(__name__)


# @pytest.fixture(autouse=True, scope="session")
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_env():
    # Configura el entorno de prueba
    os.environ["ENV"] = "test"
    load_dotenv(dotenv_path="test.env")
    setup_logging()
    logger.info("🟢 Test environment ready")

    # Prompt environment values..
    for key, value in os.environ.items():
        logger.info(f"ENV {key}={value}")
    settings = getAppSettings()

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
async def dbsession() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession instance from the async generator returned by get_session().

    `get_session()` returns an async generator / context manager. Use `async with`
    to enter it and yield the actual `AsyncSession` instance so tests can `await`
    queries directly on the session.
    """
    # Use AsyncSessionLocal directly because `get_session()` returns an async
    # generator, not an async context manager. Using AsyncSessionLocal() here
    # lets us `async with` the session and yield the actual AsyncSession.
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
