# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-07

### Added

#### Configuration Management

- AppSettings singleton with reload support in `app/core/settings.py`
- resolve_env_file() for environment-based configuration (dev/test/prod)
- 18 unit tests for settings (resolve_env_file and getAppSettings)
- ✅ 100% code coverage for settings module

#### API Foundation

- BaseRouter abstract class for extensible router pattern
- RouterRegistry for managing multiple routers
- PingRouter with health check endpoint (/ping)
- 6 unit tests for router components
- 6 functional tests for endpoints and app lifecycle

#### Testing & Quality

- pytest configuration with 85% coverage gate
- Lifespan context manager with logging setup
- 3 unit tests for lifespan hook
- mypy strict mode enabled
- Ruff linting with auto-format
- 35 total tests, 1 skipped (unimplemented feature)

#### Documentation

- CHANGELOG.md (this file)
- Comprehensive testing guide in docstrings
- Type hints throughout all modules

### Architecture

- Clean Architecture: Core + Infrastructure separation
- Dependency Injection pattern established
- Type-safe codebase (mypy strict)
- Singleton Configuration pattern

### Quality Metrics

- ✅ 100% code coverage (35 tests passing)
- ✅ Ruff: All checks passed
- ✅ mypy: Strict mode, no issues
- ✅ Python 3.12+ compliant

---

## Future Releases

### [0.2.0] - Planned

- Database layer (SQLAlchemy + SQLModel)
- Repository pattern implementation
- UseCase base classes
- Core domain entities

### [0.3.0] - Planned

- API route handlers integration
- Error handling strategy
- Logging configuration expansion

### [1.0.0] - Planned

- Full Clean Architecture implementation
- Complete test coverage (100%)
- Production-ready deployment

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking API changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

To update version:

```bash
# Update pyproject.toml version field
# Create git tag: git tag v0.1.0
# Push tag: git push origin v0.1.0
```
