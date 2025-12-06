import pytest

from app.core import settings as settings_mod


@pytest.fixture(autouse=True)
def clear_app_settings_after_test():
    """Autouse fixture that ensures AppSettings cache is cleared after each test.

    This prevents tests that mutate environment variables from leaking configuration
    into other tests and reduces cognitive overhead for test authors.
    """
    yield
    # Teardown: clear cached settings using public API when available
    if hasattr(settings_mod, "clearAppSettings"):
        settings_mod.clearAppSettings()
    else:
        settings_mod._config = None
