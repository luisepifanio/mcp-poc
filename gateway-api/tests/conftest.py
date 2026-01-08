import logging
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from app.core.logconfig import setup_logging
from app.core.settings import AppSettings

# Get a logger for this module
logger = logging.getLogger(__name__)


# @pytest.fixture(autouse=True, scope="session")
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_env() -> AsyncGenerator[None, None]:
    # Setup the test environment
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

    settings: AppSettings | None = None
    # Clear cached settings and obtain a fresh instance (use new reload API)
    if hasattr(settings_mod, "getAppSettings"):
        settings = settings_mod.getAppSettings(reload=True)
    else:
        # Fallback: direct manipulation of internal cache
        settings_mod._config = None
        settings = settings_mod.getAppSettings()

    assert settings is not None, "In a healthy test, AppSettings is set"
    logger.info(f"🟢 Test AppSettings loaded: env={settings.env}")

    # Yielding tests
    yield

    ## Tear down if needed after tests complete


@pytest.fixture(autouse=True, scope="function")
def value_inject() -> str:
    return "injected_value"
