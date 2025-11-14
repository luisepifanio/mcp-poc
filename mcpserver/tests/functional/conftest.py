import logging
import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.settings import getAppSettings

# Get a logger for this module
logger = logging.getLogger(__name__)


# @pytest.fixture(autouse=True, scope="session")
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_env():
    # Configura el entorno de prueba
    os.environ["ENV"] = "test"
    load_dotenv(dotenv_path="test.env")

    # load environment variables from test.env file

    # Prompt environment values..
    for key, value in os.environ.items():
        logger.debug(f"ENV {key}={value}")
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
def http_client() -> TestClient:
    from app.infrastructure.api.main import app

    return TestClient(app)


@pytest.fixture(autouse=True, scope="session")
def fix_session():
    # logger.info("INFO")
    # logger.debug("DEBUG")
    # logger.warning("WARNING")
    # logger.error("ERROR")
    # logger.critical("CRITICAL")

    logger.debug("Session setup")
    yield
    logger.debug("Session teardown")


@pytest.fixture(autouse=True, scope="module")
def fix_module():
    logger.debug("Module setup")
    yield
    logger.debug("Module teardown")


@pytest.fixture(autouse=True, scope="function")
def fix_function():
    logger.debug("Function setup")
    yield
    logger.debug(" Function teardown")
