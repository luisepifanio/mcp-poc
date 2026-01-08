import os

from pydantic_settings import BaseSettings, SettingsConfigDict


def resolve_env_file() -> str | None:
    env_value = os.getenv("ENV", "").lower()
    if env_value in ("development", "dev", "local"):
        return "local.env"
    elif env_value in ("test", "testing"):
        return "test.env"
    else:
        return None  # Producción, no inyectar archivo .env


class AppSettings(BaseSettings):
    env: str = "development"
    log_level: str = "DEBUG"

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


_config: AppSettings | None = None


def getAppSettings(reload: bool = False) -> AppSettings:
    """Return the singleton AppSettings instance.

    If `reload` is True the cached instance is cleared and re-created. This
    keeps a simple, backward-compatible API for callers while allowing tests
    and integration fixtures to request a fresh configuration.
    """
    global _config
    if reload:
        clearAppSettings()
    if not _config or _config is None:
        _config = AppSettings()  # pyright: ignore[reportCallIssue]
    return _config


def clearAppSettings() -> None:
    """Clear the cached AppSettings. Useful for tests that change env vars.

    Use `getAppSettings(reload=True)` as a convenience instead of calling this
    directly when needed.
    """
    global _config
    _config = None


# NOTE: `getAppSettings` now supports `reload: bool` directly. The older
# wrapper was removed to keep a single API surface.
