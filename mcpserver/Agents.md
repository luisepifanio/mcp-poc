|                  |                                                                                                                      |
| ---------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Project Name** | MCP Server Backend                                                                                                   |
| **Description**  | Backend Python con Clean Architecture, testing con pytest y CI/CD con GitHub Actions. Parte de un proyecto monorepo. |
| **Domain**       | Backend Service                                                                                                      |
| **Collection**   | Monorepo MCP POC                                                                                                     |
| **Last Updated** | 2024-12-10                                                                                                           |

---

# MCP Server Backend - Development Guide

## Resumen del Proyecto

Este proyecto es un backend Python estructurado siguiendo principios de **Clean Architecture** (Arquitectura Limpia), con una clara separación entre capas de negocio, infraestructura y presentación. El sistema utiliza FastAPI para exponer APIs REST, SQLAlchemy/SQLModel para persistencia de datos, y Scrapy para scraping. Forma parte de un monorepo más amplio dedicado a pruebas de concepto con Model Context Protocol (MCP).

### Principios Clave

- **Clean Architecture**: Separación estricta entre capas (core/domain, use cases, infrastructure)
- **Dependency Inversion**: Las dependencias apuntan hacia el dominio, no hacia la infraestructura
- **Testing Comprehensive**: Suite completa de tests unitarios, de integración y funcionales
- **Type Safety**: Uso extensivo de type hints y validación con Pydantic
- **Configuración por Entornos**: Manejo de configuración mediante variables de entorno con soporte multi-entorno

---

## Stack Tecnológico

- **Lenguaje**: Python 3.12+
- **Framework Web**: FastAPI 0.121.0+ (con soporte estándar)
- **ORM/Database**: SQLAlchemy 2.0.44+ con SQLModel 0.0.27
- **Base de Datos**: SQLite (desarrollo/testing), configurable para PostgreSQL/MySQL (producción)
- **Scraping**: Scrapy con Playwright (scrapy-playwright)
- **Gestión de Paquetes**: uv
- **Testing**: pytest 9.0+ con pytest-asyncio, pytest-cov, pytest-mock
- **Linting/Formatting**: Ruff 0.14.4+
- **Type Checking**: mypy (strict mode)
- **Logging**: logging estándar de Python + python-json-logger + colorlog
- **CI/CD**: GitHub Actions (configuración en progreso)

---

## Estructura del Proyecto

```
mcpserver/
├── app/                          # Código fuente principal
│   ├── __init__.py
│   ├── main.py                   # Entry point de la aplicación
│   ├── errors.py                 # Definición de errores personalizados
│   │
│   ├── core/                     # Capa de dominio y lógica de negocio
│   │   ├── entities.py           # Entidades del dominio (modelos de negocio)
│   │   ├── interfaces.py         # Contratos/interfaces (Repository, UoW)
│   │   ├── repositories.py       # Interfaces abstractas de repositorios
│   │   ├── respository_event.py  # Repositorio específico para eventos
│   │   ├── unit_of_work.py       # Patrón Unit of Work (abstracción)
│   │   ├── usecase.py            # Clases base para casos de uso
│   │   ├── settings.py           # Configuración de la aplicación
│   │   ├── logconfig.py          # Configuración de logging
│   │   │
│   │   └── usecases/             # Casos de uso concretos
│   │       ├── course_usecases.py
│   │       └── event_usecases.py
│   │
│   └── infrastructure/           # Capa de infraestructura
│       ├── api/                  # Capa de presentación (API REST)
│       │   ├── main.py           # Configuración FastAPI
│       │   └── routes.py         # Definición de rutas/endpoints
│       │
│       ├── db/                   # Implementaciones de persistencia
│       │   ├── connection.py     # Gestión de conexiones a BD
│       │   ├── repository.py     # Implementación genérica de repositorios
│       │   ├── repository_event.py # Repositorio de eventos (implementación)
│       │   ├── unit_of_work.py   # Implementación concreta de UoW
│       │   │
│       │   └── models/           # Modelos de base de datos (SQLModel)
│       │       ├── __init__.py
│       │       └── default.py
│       │
│       └── scrapy_spider/        # Spiders de Scrapy
│           ├── middlewares.py
│           ├── repository.py
│           └── spiders/
│               └── course_spider.py
│
├── tests/                        # Suite de testing
│   ├── conftest.py               # Fixtures globales y configuración pytest
│   ├── unit/                     # Tests unitarios (lógica aislada)
│   │   ├── test_errors_unit.py
│   │   ├── test_event_enqueue_unit.py
│   │   ├── test_repository_course_unit.py
│   │   ├── test_repository_event_unit.py
│   │   ├── test_respository_event_logic_unit.py
│   │   ├── test_settings_unit.py
│   │   └── test_unit_of_work_unit.py
│   │
│   └── functional/               # Tests funcionales (integración completa)
│       ├── conftest.py
│       ├── test_courses.py
│       ├── test_event_enqueue_functional.py
│       ├── test_event_enqueue_idempotency.py
│       ├── test_event_enqueue_validation_and_conflict.py
│       ├── test_get_by_external_uuid_repository.py
│       ├── test_getmany_event_repository.py
│       ├── test_savemany_event_repository.py
│       └── test_delete_multi_event_repository.py
│
├── var/lib/                      # Datos locales (SQLite, logs)
├── pyproject.toml                # Configuración del proyecto y dependencias
├── Dockerfile                    # Containerización
├── README.md                     # Documentación para humanos
├── env.example                   # Plantilla de variables de entorno
├── local.env                     # Variables de entorno para desarrollo local
└── test.env                      # Variables de entorno para testing
```

---

## Guías de Desarrollo

### Principios de Clean Architecture

1. **Separación de Capas**:

   - `core/`: Contiene la lógica de negocio pura (entities, use cases, interfaces)
   - `infrastructure/`: Implementaciones técnicas (BD, API, scrapers)
   - Las dependencias fluyen de afuera hacia adentro (infrastructure → core)

2. **Inversión de Dependencias**:

   - Los use cases dependen de interfaces (abstracciones) definidas en `core/interfaces.py`
   - Las implementaciones concretas viven en `infrastructure/`
   - Uso del patrón Repository y Unit of Work para abstraer la persistencia

3. **Testing por Capas**:
   - **Unit tests**: Validan lógica de negocio aislada con mocks
   - **Functional tests**: Validan flujos completos con dependencias reales (BD en memoria)

### Convenciones de Código

#### Python Best Practices

- **Type Hints**: Siempre usar anotaciones de tipos en firmas de funciones y métodos
- **Pydantic Models**: Para validación de datos de entrada/salida (settings, DTOs)
- **Naming Conventions**:
  - `snake_case` para funciones, variables y nombres de archivos
  - `PascalCase` para clases
  - Prefijos `_` para métodos/atributos privados
- **Docstrings**: Documentar clases públicas y métodos complejos
- **Error Handling**: Usar `result` library para manejo funcional de errores en use cases

#### Linting y Formatting

Este proyecto usa **Ruff** como linter y formatter unificado:

```bash
# Ejecutar linting
uv run ruff check .

# Auto-fix problemas corregibles
uv run ruff check --fix .

# Format código
uv run ruff format .
```

**Configuración (pyproject.toml)**:

- Line length: 90 caracteres
- Target: Python 3.12
- Reglas activas: E (pycodestyle errors), W (warnings), F (pyflakes), I (isort), B (bugbear), C4 (comprehensions), UP (pyupgrade)

#### Type Checking

```bash
# Ejecutar mypy
uv run mypy app
```

Configuración: `strict = true` (modo estricto habilitado)

---

## Configuración de Entornos

### Sistema de Configuración Multi-Entorno

El proyecto utiliza un sistema basado en la variable `ENV` para cargar automáticamente el archivo de configuración correcto:

| Valor de `ENV`                | Archivo Cargado | Uso                                      |
| ----------------------------- | --------------- | ---------------------------------------- |
| `development`, `dev`, `local` | `local.env`     | Desarrollo local                         |
| `test`, `testing`             | `test.env`      | Ejecución de tests                       |
| (otro valor o no definido)    | Ninguno         | Producción (vars de entorno del sistema) |

**Ubicación**: `app/core/settings.py`

### Variables de Entorno Requeridas

Crear archivos `.env` según el entorno (usar `env.example` como plantilla):

```bash
# Valores típicos para local.env
ENV=development
DATABASE_URL=sqlite:///./var/lib/database.sqlite
LOG_LEVEL=DEBUG
```

```bash
# Valores típicos para test.env
ENV=test
DATABASE_URL=sqlite:///:memory:
LOG_LEVEL=WARNING
```

**⚠️ Importante**:

- El sistema cachea la configuración en un singleton (`getAppSettings()`)
- Para tests que modifiquen variables de entorno, usar `clearAppSettings()` o `getAppSettings(reload=True)`
- Existe un fixture global en `tests/conftest.py` que limpia la caché automáticamente

---

## Comandos de Desarrollo

### Instalación

```bash
# Instalar dependencias de producción
uv sync

# Instalar con dependencias de desarrollo
uv sync --group dev
```

### Ejecución del Servidor

```bash
# Modo desarrollo (auto-reload)
uv run fastapi dev
```

Acceso a la API:

- **Base URL**: http://127.0.0.1:8000
- **Docs (Swagger)**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

---

## Testing

### Comandos de Testing

#### Ejecutar Todos los Tests

```bash
# Desde la raíz del proyecto (recomendado)
uv run pytest

# Con output verboso
uv run pytest -v

# Con output silencioso (solo failures)
uv run pytest -q
```

#### Ejecutar Tests por Tipo

```bash
# Solo tests unitarios
uv run pytest tests/unit/

# Solo tests funcionales
uv run pytest tests/functional/

# Test específico
uv run pytest tests/unit/test_settings_unit.py

# Test específico por nombre
uv run pytest -k "test_nombre_especifico"
```

#### Cobertura de Código

```bash
# Generar reporte de cobertura (configurado por defecto en pytest)
uv run pytest

# Ver reporte HTML (generado en dist/reports/coverage/html/)
open dist/reports/coverage/html/index.html
```

**Configuración de Cobertura**:

- Objetivo de cobertura: Sin mínimo definido (actualmente comentado `fail_under = 90`)
- Branch coverage: Habilitado
- Reportes: Terminal, HTML, XML

### Estructura de Testing

#### Tests Unitarios (`tests/unit/`)

- **Objetivo**: Validar lógica de negocio aislada
- **Características**:
  - Uso extensivo de mocks (pytest-mock, unittest.mock)
  - No requieren conexiones a BD reales
  - Rápidos de ejecutar
  - Validan contratos de interfaces

**Ejemplo típico**:

```python
def test_use_case_logic(mocker):
    # Mock de dependencias
    mock_repository = mocker.Mock(spec=IRepository)
    mock_repository.get_by_id.return_value = some_entity

    # Ejecutar use case
    use_case = MyUseCase(repository=mock_repository)
    result = use_case.execute(param)

    # Validaciones
    assert result.is_ok()
    mock_repository.get_by_id.assert_called_once_with(expected_id)
```

#### Tests Funcionales (`tests/functional/`)

- **Objetivo**: Validar flujos completos end-to-end
- **Características**:
  - Usan base de datos real (SQLite in-memory en tests)
  - Validan integración entre capas
  - Prueban comportamiento desde la API hasta la BD
  - Fixture global para limpiar estado entre tests

**Ejemplo típico**:

```python
async def test_create_course_functional(async_client, db_session):
    # Llamada real a API
    response = await async_client.post(
        "/api/courses",
        json={"name": "Test Course", "description": "..."}
    )

    # Validaciones
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Course"

    # Verificar en BD
    course = await db_session.get(Course, data["id"])
    assert course is not None
```

### Fixtures Importantes

#### Fixture Global de Limpieza de Settings

**Ubicación**: `tests/conftest.py`

```python
@pytest.fixture(autouse=True)
def clear_app_settings():
    """Limpia la caché de settings después de cada test."""
    yield
    from app.core import settings as settings_mod
    settings_mod.clearAppSettings()
```

Este fixture se ejecuta automáticamente después de cada test para evitar contaminación de configuración entre tests.

#### Tests que Modifican Variables de Entorno

Si necesitas modificar variables de entorno en un test:

```python
def test_custom_config(monkeypatch):
    # Modificar env var
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # Recargar configuración
    from app.core.settings import getAppSettings
    settings = getAppSettings(reload=True)

    # Validaciones
    assert settings.database_url == "sqlite:///:memory:"
```

### Consideraciones de Testing

1. **No modificar `PYTHONPATH` manualmente**: El `pyproject.toml` ya configura `pythonpath = ["."]`
2. **Ejecutar desde la raíz**: Todos los comandos de pytest deben ejecutarse desde `/mcpserver`
3. **Async tests**: Configurado `asyncio_mode = "auto"` para tests asíncronos automáticos
4. **Warnings**: Configurados filtros para ignorar warnings conocidos de SQLAlchemy y Pydantic

---

## Patterns y Arquitectura

### Repository Pattern

**Definición**: `app/core/interfaces.py` o `app/core/repositories.py`

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar('T')

class IRepository(ABC, Generic[T]):
    @abstractmethod
    async def get_by_id(self, id: int) -> T | None:
        pass

    @abstractmethod
    async def save(self, entity: T) -> T:
        pass
```

**Implementación**: `app/infrastructure/db/repository.py`

Los repositorios concretos implementan estas interfaces usando SQLAlchemy/FastCRUD.

### Unit of Work Pattern

**Definición**: `app/core/unit_of_work.py`

```python
class IUnitOfWork(ABC):
    @abstractmethod
    async def __aenter__(self):
        pass

    @abstractmethod
    async def __aexit__(self, *args):
        pass

    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass
```

**Uso en Use Cases**:

```python
async def execute(self, data: InputDTO) -> Result[OutputDTO, Error]:
    async with self.unit_of_work as uow:
        # Operaciones transaccionales
        entity = await uow.repository.save(entity)
        await uow.commit()
        return Ok(OutputDTO.from_entity(entity))
```

### Use Case Pattern

**Base**: `app/core/usecase.py`

Todos los use cases heredan de una clase base que define la estructura:

```python
class UseCase(ABC, Generic[TInput, TOutput]):
    @abstractmethod
    async def execute(self, input_data: TInput) -> Result[TOutput, Error]:
        pass
```

Esto garantiza:

- Consistencia en la interfaz de use cases
- Manejo de errores con `Result` type (Ok/Err)
- Type safety en entrada y salida

---

## Logging

### Sistema de Logging

El proyecto utiliza el módulo `logging` estándar de Python con bibliotecas adicionales para formateo:

- **logging**: Módulo estándar de Python para logging
- **python-json-logger**: Formato JSON para logs estructurados
- **colorlog**: Logs coloreados en desarrollo

**Configuración**: `app/core/logconfig.py`

### Uso en Código

```python
import logging

# Buena práctica: crear logger con el nombre del módulo
logger = logging.getLogger(__name__)

# Niveles de logging
logger.debug("Mensaje de debug detallado")
logger.info("Información general")
logger.warning("Advertencia")
logger.error("Error recuperable")
logger.exception("Error con traceback completo")
```

### Configuración por Entorno

El nivel de logging se controla mediante la variable `LOG_LEVEL` en archivos `.env`:

- **Development**: `DEBUG` (todos los mensajes)
- **Testing**: `WARNING` (solo warnings y errores)
- **Production**: `INFO` o `WARNING` (según necesidad)

---

## CI/CD con GitHub Actions

### Estado Actual

El proyecto está configurado para ejecutar CI/CD mediante GitHub Actions (en progreso).

### Workflow Típico (a implementar)

```yaml
# .github/workflows/test.yml (ejemplo)
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.12"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --group dev

      - name: Run linting
        run: uv run ruff check .

      - name: Run type checking
        run: uv run mypy app

      - name: Run tests
        run: uv run pytest

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./dist/reports/coverage/coverage.xml
```

### Pre-commit Hooks (recomendado)

Para garantizar calidad antes de commits, se recomienda configurar pre-commit hooks:

```bash
# Instalar pre-commit
uv add --dev pre-commit

# Instalar hooks
uv run pre-commit install
```

**Archivo `.pre-commit-config.yaml`** (ejemplo):

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

---

## Contexto del Monorepo

### Ubicación en Monorepo

Este backend (`mcpserver`) es un componente dentro de un monorepo más amplio dedicado a pruebas de concepto con **Model Context Protocol (MCP)**.

### Consideraciones para Agentes

1. **Path Awareness**: Siempre ejecutar comandos desde la raíz del proyecto (`/mcpserver`), no desde la raíz del monorepo
2. **Dependencias Compartidas**: Verificar si existen dependencias compartidas a nivel monorepo
3. **CI/CD**: Los workflows pueden estar configurados a nivel monorepo (path filters)
4. **Imports**: Todos los imports deben usar rutas absolutas desde `app.` (ej: `from app.core.entities import ...`)

---

## Gestión de Errores

### Sistema de Errores

**Definición**: `app/errors.py`

El proyecto define errores personalizados que extienden excepciones de Python y FastAPI:

```python
from fastapi import HTTPException

class DomainError(Exception):
    """Base exception para errores de dominio"""
    pass

class NotFoundError(DomainError, HTTPException):
    def __init__(self, entity: str, id: Any):
        self.status_code = 404
        self.detail = f"{entity} with id {id} not found"
        super().__init__(self.detail)
```

### Manejo con Result Type

Los use cases usan `result` library para manejo funcional de errores:

```python
from result import Result, Ok, Err

async def execute(self, id: int) -> Result[CourseDTO, NotFoundError]:
    course = await self.repository.get_by_id(id)
    if course is None:
        return Err(NotFoundError("Course", id))
    return Ok(CourseDTO.from_entity(course))
```

**En rutas (infrastructure/api)**:

```python
@router.get("/courses/{id}")
async def get_course(id: int, use_case: GetCourseUseCase = Depends()):
    result = await use_case.execute(id)

    if result.is_err():
        raise result.unwrap_err()  # Raises HTTPException

    return result.unwrap()  # Returns CourseDTO
```

---

## Base de Datos

### Tecnologías

- **ORM**: SQLAlchemy 2.0+ (async)
- **Models**: SQLModel (combina Pydantic + SQLAlchemy)
- **Migrations**: (Pendiente: Alembic, actualmente excluido en configuración)

### Modelos

**Ubicación**: `app/infrastructure/db/models/`

```python
from sqlmodel import SQLModel, Field

class CourseModel(SQLModel, table=True):
    __tablename__ = "courses"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    description: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Conexión a Base de Datos

**Gestión**: `app/infrastructure/db/connection.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG"
)

async def get_session() -> AsyncSession:
    async with AsyncSession(engine) as session:
        yield session
```

### Migraciones

**Estado**: Pendiente de configurar Alembic

**Cuando se implemente**:

```bash
# Crear migración
uv run alembic revision --autogenerate -m "descripción"

# Aplicar migraciones
uv run alembic upgrade head

# Revertir última migración
uv run alembic downgrade -1
```

---

## Scraping con Scrapy

### Componentes

**Spiders**: `app/infrastructure/scrapy_spider/spiders/`

Ejemplo: `course_spider.py` para scraping de cursos educativos.

**Middlewares**: `app/infrastructure/scrapy_spider/middlewares.py`

**Repository Integration**: `app/infrastructure/scrapy_spider/repository.py` - Conecta scrapy con el sistema de repositorios

### Ejecución de Spiders

```bash
# Ejecutar spider específico
scrapy crawl course_spider

# Con parámetros
scrapy crawl course_spider -a url=https://example.com

# Guardar resultados
scrapy crawl course_spider -o output.json
```

### Configuración de Playwright

El proyecto usa `scrapy-playwright` para scraping de páginas dinámicas (JavaScript):

```python
# En settings de Scrapy
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"
```

---

## Docker

### Dockerfile

**Ubicación**: `/Dockerfile` (raíz del proyecto)

### Build y Ejecución

```bash
# Build de imagen
docker build -t mcpserver:latest .

# Ejecutar contenedor
docker run -p 8000:8000 \
  -e ENV=production \
  -e DATABASE_URL=sqlite:///./data/database.sqlite \
  mcpserver:latest

# Con docker-compose (si existe)
docker-compose up
```

### Consideraciones

- Volúmenes para persistencia de BD SQLite: `./var/lib:/app/var/lib`
- Variables de entorno según ambiente
- Multi-stage builds para optimizar tamaño de imagen

---

## Troubleshooting

### Problema: Tests fallan con `ModuleNotFoundError`

**Solución**:

- Verificar que ejecutas pytest desde la raíz de `/mcpserver`
- Verificar `pythonpath = ["."]` en `[tool.pytest.ini_options]` de `pyproject.toml`
- No configurar `PYTHONPATH` manualmente

### Problema: Configuración incorrecta en tests

**Solución**:

- Verificar que `test.env` esté configurado correctamente
- Usar `getAppSettings(reload=True)` si modificas env vars en el test
- Verificar que el fixture `clear_app_settings` esté activo (debería ser automático)

### Problema: Errores de tipo con mypy

**Solución**:

- Ejecutar `uv run mypy app --show-error-codes` para ver códigos de error específicos
- Añadir type hints donde falten
- Usar `# type: ignore[code]` como último recurso (documentar por qué)

### Problema: Coverage no refleja cambios

**Solución**:

- Eliminar archivos `.coverage` antiguos: `rm .coverage`
- Re-ejecutar tests: `uv run pytest`
- Verificar que los paths en `[tool.coverage.paths]` sean correctos

### Problema: Linter Ruff reporta errores inesperados

**Solución**:

- Actualizar Ruff: `uv add --dev ruff@latest`
- Verificar configuración en `pyproject.toml` → `[tool.ruff.lint]`
- Añadir reglas a `ignore` si son falsos positivos

---

## Recursos y Referencias

### Documentación Oficial

- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy**: https://docs.sqlalchemy.org/
- **SQLModel**: https://sqlmodel.tiangolo.com/
- **Pytest**: https://docs.pytest.org/
- **Ruff**: https://docs.astral.sh/ruff/
- **Scrapy**: https://docs.scrapy.org/
- **Playwright**: https://playwright.dev/python/

### Patrones y Arquitectura

- **Clean Architecture**: "Clean Architecture" by Robert C. Martin
- **Repository Pattern**: Martin Fowler - https://martinfowler.com/eaaCatalog/repository.html
- **Unit of Work**: Martin Fowler - https://martinfowler.com/eaaCatalog/unitOfWork.html

### Python Best Practices

- **PEP 8**: https://pep8.org/
- **Python Type Hints**: https://docs.python.org/3/library/typing.html
- **Pydantic**: https://docs.pydantic.dev/

---

## Convenciones de Commits y PRs

### Formato de Commits

Usar **Conventional Commits**:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Tipos comunes**:

- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `refactor`: Refactorización de código
- `test`: Añadir o modificar tests
- `docs`: Cambios en documentación
- `chore`: Tareas de mantenimiento
- `perf`: Mejoras de performance
- `style`: Cambios de formato (no afectan lógica)

**Ejemplos**:

```
feat(courses): add endpoint to list all courses
fix(events): correct idempotency check in event repository
test(unit): add tests for settings cache clearing
refactor(core): extract common repository logic to base class
docs(readme): update testing instructions
```

### Pull Requests

**Título**: `[mcpserver] <Descripción breve>`

**Antes de crear PR**:

```bash
# 1. Ejecutar linting
uv run ruff check --fix .
uv run ruff format .

# 2. Ejecutar type checking
uv run mypy app

# 3. Ejecutar tests completos
uv run pytest

# 4. Verificar cobertura
# (generada automáticamente con pytest)
```

**Checklist para PR**:

- [ ] Todos los tests pasan
- [ ] Cobertura de código no disminuye
- [ ] Linting y formatting aplicados
- [ ] Type hints añadidos donde corresponda
- [ ] Documentación actualizada si es necesario
- [ ] Commits siguen convención establecida
- [ ] Variables de entorno documentadas en `env.example` si se añaden nuevas

---

## Notas Adicionales para Agentes

### Cuando Modificas Código

1. **Respeta la arquitectura**: No mezcles lógica de negocio con infraestructura
2. **Sigue el patrón existente**: Si hay un repositorio para `Course`, seguir el mismo patrón para nuevas entidades
3. **Añade tests**: Cada nuevo use case debe tener tests unitarios y funcionales
4. **Type safety**: Todas las funciones públicas deben tener type hints completos

### Cuando Añades Nuevas Features

1. **Entities primero**: Definir entidades de dominio en `app/core/entities.py`
2. **Interfaces después**: Definir contratos en `app/core/interfaces.py` o `repositories.py`
3. **Use cases**: Implementar lógica en `app/core/usecases/`
4. **Implementaciones**: Crear implementaciones concretas en `app/infrastructure/`
5. **Rutas API**: Exponer funcionalidad en `app/infrastructure/api/routes.py`
6. **Tests**: Añadir cobertura en `tests/unit/` y `tests/functional/`

### Cuando Investigas el Código

1. **Buscar por responsabilidad**:

   - Lógica de negocio → `app/core/`
   - Persistencia → `app/infrastructure/db/`
   - API → `app/infrastructure/api/`
   - Scraping → `app/infrastructure/scrapy_spider/`

2. **Entender flujo típico**:

   ```
   Request → Route → Use Case → Repository (interface)
                                        ↓
                                 DB Repository (implementation)
                                        ↓
                                   Database
   ```

3. **Verificar tests**: Los tests funcionales son excelente documentación de cómo usar el sistema

### Ejecución de Comandos

**Siempre usar `uv run` como prefijo** para asegurar que se usa el entorno correcto:

```bash
# ✅ Correcto
uv run pytest
uv run ruff check .
uv run python -m app.main

# ❌ Incorrecto (puede usar Python incorrecto)
pytest
ruff check .
python -m app.main
```

---

## Changelog

### v0.1.0 (2024-12-10)

- Versión inicial del documento Agents.md
- Arquitectura base con Clean Architecture
- Sistema de testing con pytest (unitario + funcional)
- Configuración multi-entorno
- Integración con FastAPI, SQLAlchemy, Scrapy
- Configuración de linting con Ruff
- Type checking con mypy (strict mode)

---

**Nota Final**: Este documento es específico para agentes de IA y debe mantenerse actualizado con cambios significativos en la estructura del proyecto, comandos, o convenciones. Para documentación orientada a humanos, consultar `README.md`.
