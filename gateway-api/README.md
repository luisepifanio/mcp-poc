# Gateway API

> Backend Python REST API con Clean Architecture, pytest testing, y CI/CD ready.

## 📊 Project Status

| Metric       | Value                    |
| ------------ | ------------------------ |
| Tests        | 35 passing, 1 skipped ✅ |
| Coverage     | 100% ✅                  |
| Python       | 3.12+ ✅                 |
| Code Quality | Ruff + mypy strict ✅    |
| Status       | Stable Baseline v0.1.0   |

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- `uv` package manager

### Setup

```bash
# 1. Navigate to project
cd gateway-api

# 2. Install dependencies
uv sync --group dev

# 3. Configure environment
cp env.example local.env
# Edit local.env with your values

# 4. Run tests
uv run pytest

# 5. Start development server
uv run fastapi dev

# 6. View API documentation
# Open http://127.0.0.1:8000/docs
```

## 📁 Project Structure

```
app/
├── core/                      # Core business logic
│   ├── settings.py           # Configuration management
│   ├── logconfig.py          # Logging setup
│   └── __init__.py
│
└── infrastructure/            # Technical implementations
    └── api/                   # FastAPI layer
        ├── main.py           # App bootstrap
        ├── base_router.py    # Abstract router
        ├── ping_router.py    # Health check
        └── router_registry.py # Router management

tests/
├── unit/                      # Isolated unit tests
│   ├── test_lifespan.py      # App lifespan hooks
│   ├── test_settings.py      # Configuration tests
│   └── test_router_components.py  # Router tests
│
└── functional/                # End-to-end tests
    ├── test_ping.py
    └── test_ping_endpoint.py
```

## 🔧 Development

### Run Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/unit/test_settings.py -v

# With coverage
uv run pytest --cov=app

# Watch mode
uv run pytest --tb=short -k "test_name"
```

### Code Quality

```bash
# Lint (auto-fix)
uv run ruff check --fix .

# Format
uv run ruff format .

# Type check
uv run mypy app
```

### Run Server

```bash
# Development with hot reload
uv run fastapi dev

# Production mode
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📚 Documentation

### Key Principles

1. **Clean Architecture**: Core domain logic separated from infrastructure
2. **Type Safety**: Strict mypy, all functions have type hints
3. **Testing First**: 100% coverage on core modules
4. **Code Quality**: Ruff linting mandatory before commits
5. **Dependency Injection**: All dependencies inyected, never hardcoded

### Configuration

Configuration is managed through `AppSettings` singleton pattern:

```python
from app.core.settings import getAppSettings

settings = getAppSettings()
print(settings.env)      # development, test, or production
print(settings.log_level) # DEBUG, INFO, etc.
```

Environment detection:

- `ENV=development|dev|local` → uses `local.env`
- `ENV=test|testing` → uses `test.env`
- `ENV=production` → no .env file (use system variables)

### Router Pattern

Add new endpoints easily:

```python
from app.infrastructure.api.base_router import BaseRouter
from fastapi import APIRouter

class MyRouter(BaseRouter):
    def register_routes(self) -> None:
        @self.router.get("/my-endpoint")
        async def my_endpoint() -> dict:
            return {"message": "hello"}

# In app/infrastructure/api/main.py
from .my_router import MyRouter
registry.add(MyRouter())
```

## 🧪 Testing Guide

### Unit Tests

- Located in `tests/unit/`
- Test isolated functions with mocks
- Fast execution (< 1ms per test)
- Target: app/core/\* modules

### Functional Tests

- Located in `tests/functional/`
- End-to-end with real components
- TestClient for HTTP testing
- Target: API endpoints, integrations

### Adding Tests

```python
# tests/unit/test_my_module.py
import pytest
from app.core.my_module import my_function

def test_my_function_returns_expected_value() -> None:
    result = my_function("input")
    assert result == "expected"

@pytest.mark.asyncio
async def test_async_function() -> None:
    result = await async_function()
    assert result is not None
```

## 📦 Dependencies

### Production

- **FastAPI**: Web framework
- **Pydantic**: Data validation
- **SQLModel**: ORM (planned)
- **tenacity**: Retry logic
- **result**: Result type for error handling

### Development

- **pytest**: Testing framework
- **mypy**: Type checking
- **ruff**: Linting & formatting
- **pytest-asyncio**: Async test support

## 🔐 Security

- Environment variables for sensitive data (see `.env.example`)
- Type hints prevent injection vulnerabilities
- No hardcoded credentials or secrets

## 📝 Versioning

This project follows [Semantic Versioning](https://semver.org/):

- `0.1.0` - Stable baseline (current)
- `0.2.0` - Database layer (planned)
- `1.0.0` - Production ready (planned)

See [CHANGELOG.md](CHANGELOG.md) for detailed history.

## 🤝 Contributing

### Workflow

1. Create feature branch from `main`
2. Implement with tests (100% coverage target)
3. Run quality gates:
   ```bash
   uv run ruff check . && uv run mypy app && uv run pytest
   ```
4. Create PR with descriptive title
5. Merge after review

### Commit Messages

Follow Conventional Commits:

```
feat(scope): add new feature
fix(scope): fix bug
test(scope): add/update tests
docs(scope): update documentation
```

## 📖 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [pytest Documentation](https://docs.pytest.org/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

## 📄 License

[Specify your license here]

## 📞 Support

For issues, questions, or contributions, please open an issue in the repository.
