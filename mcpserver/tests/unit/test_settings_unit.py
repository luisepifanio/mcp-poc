from app.core import settings as settings_mod


def test_resolve_env_file_various(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    assert settings_mod.resolve_env_file() == "local.env"

    monkeypatch.setenv("ENV", "dev")
    assert settings_mod.resolve_env_file() == "local.env"

    monkeypatch.setenv("ENV", "test")
    assert settings_mod.resolve_env_file() == "test.env"

    monkeypatch.setenv("ENV", "production")
    assert settings_mod.resolve_env_file() is None


def test_get_app_settings_singleton(monkeypatch):
    # Ensure environment variables exist for required fields
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    # Clear cached config
    if hasattr(settings_mod, "clearAppSettings"):
        settings_mod.clearAppSettings()
    else:
        settings_mod._config = None

    try:
        s1 = settings_mod.getAppSettings()
        s2 = settings_mod.getAppSettings()

        assert s1 is s2
        assert s1.database_url == "sqlite:///:memory:"
        assert s1.log_level == "INFO"
    finally:
        # Ensure we clear the cached settings to avoid leaking into other tests
        if hasattr(settings_mod, "clearAppSettings"):
            settings_mod.clearAppSettings()
        else:
            settings_mod._config = None
