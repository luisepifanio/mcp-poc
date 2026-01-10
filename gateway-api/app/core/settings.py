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

    # Redis configuration
    redis_url: str = "redis://localhost:6379"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def redis_connection_url(self) -> str:
        """
        Build Redis connection URL from components.

        Prioritizes `redis_url` if explicitly customized.
        Otherwise, constructs from host/port/password/db components.

        Returns:
            Complete Redis connection URL
        """
        # If redis_url was customized, use it directly
        if self.redis_url != "redis://localhost:6379":
            return self.redis_url

        # Build from components (useful for K8s secrets, etc.)
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


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
