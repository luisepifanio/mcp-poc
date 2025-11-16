import os

from pydantic_settings import BaseSettings, SettingsConfigDict


def resolve_env_file():
    env_value = os.getenv("ENV", "").lower()
    if env_value in ("development", "dev", "local"):
        return "local.env"
    elif env_value in ("test", "testing"):
        return "test.env"
    else:
        return None  # Producción, no inyectar archivo .env


class AppSettings(BaseSettings):
    env: str
    database_url: str
    log_level: str

    model_config = SettingsConfigDict(
        env_file=resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


_config: AppSettings | None = None


def getAppSettings() -> AppSettings:
    global _config
    if not _config or _config is None:
        _config = AppSettings()  # pyright: ignore[reportCallIssue]
    return _config
