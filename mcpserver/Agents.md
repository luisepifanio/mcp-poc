|                  |                                                                                                                      |
| ---------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Project Name** | MCP Server Backend                                                                                                   |
| **Description**  | Backend Python con Clean Architecture, testing con pytest y CI/CD con GitHub Actions. Parte de un proyecto monorepo. |
| **Domain**       | Backend Service                                                                                                      |
| **Collection**   | Monorepo MCP POC                                                                                                     |
| **Last Updated** | 2025-12-28                                                                                                           |

---

# MCP Server Backend - Development Guide

**Nota**: Este documento es un roadmap práctico para desarrolladores humanos y agentes IA. Está diseñado para ser consultado durante el desarrollo, no solo leído al inicio.

---

## 📋 Quick Start

### Setup Inicial

```bash
# 1. Clonar y navegar
cd mcpserver

# 2. Instalar dependencias
uv sync --group dev

# 3. Configurar entorno
cp env.example local.env
# Editar local.env con tus valores

# 4. Ejecutar servidor
uv run fastapi dev

# 5. Ejecutar tests
uv run pytest
```

### URLs importantes

- **API**: http://127.0.0.1:8000
- **Docs**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

---

## 🏗️ Proyecto Overview

### Principios Core

- **Clean Architecture**: 3 capas (core/domain → usecases → infrastructure)
- **SOLID Principles**: Aplicados consistentemente en todo el diseño
  - Single Responsibility: Cada clase/módulo tiene una única razón para cambiar
  - Open/Closed: Abierto para extensión, cerrado para modificación
  - Liskov Substitution: Implementaciones intercambiables vía interfaces ABC
  - Interface Segregation: Interfaces específicas, no monolíticas
  - Dependency Inversion: Dependencias hacia abstracciones (ABC), no concretas
- **"Lo que no está, no falla"**: Mantener solo código esencial y utilizado
  - Eliminar código muerto agresivamente (funciones, clases, helpers no usados)
  - Priorizar simplicidad sobre "por si acaso"
  - Cada línea debe justificar su existencia con uso real
  - Code reviews deben cuestionar: "¿Se usa esto? ¿Es esencial?"
- **Dependency Injection**: Dependencias inyectadas, nunca instanciadas en componentes
- **Type Safety**: Tipos explícitos en TODO, mypy strict mode
- **Testing First**: Unit + Functional tests, mínimo 75% coverage

### Stack Técnico

| Componente    | Tecnología            | Versión       | Rol                           |
| ------------- | --------------------- | ------------- | ----------------------------- |
| Lenguaje      | Python                | 3.12+         | Runtime                       |
| Framework Web | FastAPI               | 0.121+        | API REST                      |
| BD/ORM        | SQLAlchemy + SQLModel | 2.0+ / 0.0.27 | Persistencia                  |
| BD Storage    | SQLite/PostgreSQL     | -             | Dev/Prod                      |
| Testing       | pytest                | 9.0+          | Tests unitarios/funcionales   |
| Linting       | Ruff                  | 0.14+         | **Obligatorio**               |
| Type Checking | mypy                  | latest        | **Obligatorio** (strict mode) |
| Logging       | logging + json-logger | std           | Structured logs               |
| Scraping      | Scrapy + Playwright   | latest        | Web scraping                  |

### Estructura Carpetas

```
app/
├── core/                      # 🧠 Lógica de negocio pura
│   ├── entities.py           # Modelos de dominio
│   ├── repositories.py       # Interfaces ABC de repositorios
│   ├── repository_event.py   # Interface ABC específica de eventos
│   ├── unit_of_work.py       # Interface ABC del patrón UnitOfWork
│   ├── usecase.py            # Clase base para UseCases
│   ├── usecases/             # Implementaciones de UseCases
│   │   ├── event_usecases.py
│   │   └── course_usecases.py
│   ├── settings.py           # Configuración
│   └── logconfig.py          # Logging setup
│
└── infrastructure/           # 🔧 Implementaciones técnicas
    ├── api/                 # 📡 Presentación (FastAPI)
    │   ├── main.py
    │   └── routes/
    ├── db/                  # 💾 Persistencia
    │   ├── models/          # SQLModel definitions
    │   ├── repository.py    # Implementación genérica
    │   ├── repository_event.py
    │   ├── unit_of_work.py
    │   └── connection.py
    ├── redis/               # 🔄 Message broker
    └── scrapy_spider/       # 🕷️ Web scraping

tests/
├── unit/                     # Tests aislados (mocks)
└── functional/               # Tests end-to-end (BD real)
```

---

## 🔄 Development Workflow

Este workflow es **REPETIBLE** - cada feature sigue estos pasos:

### Step 1: Definir Requerimientos

```
- Escribir descripción clara de la funcionalidad
- Definir criterios de aceptación
- Identificar entidades y casos de uso
```

### Step 2: Diseño de Solución

```
- Definir entidades en app/core/entities.py
- Crear interfaces ABC en app/core/repositories.py o repository_*.py
- Diseñar contrato del UseCase (Input/Output DTOs)
```

### Step 3: Implementar (Core → Infrastructure)

```
# 1. Implementar lógica en core/usecases/
async def execute(self, input: InputDTO) -> Result[OutputDTO, Error]:
    # Lógica pura, sin dependencias de infraestructura

# 2. Implementar repositorio en infrastructure/db/
class AsyncSQLAlchemyEventRepository:
    async def save_or_resolve_one(self, event: Event) -> Result[Event, Error]:
        # Implementación real con SQLAlchemy

# 3. Conectar en API (infrastructure/api/routes.py)
@router.post("/events")
async def enqueue_event(input: EnqueuedEventUseCaseInput) -> dict:
    result = await use_case.execute(input)
    # ...
```

### Step 4: Testing Validatorio (Unit + Functional)

```
# Unit: Lógica aislada con mocks
def test_use_case_logic(uow_mock):
    result = await use_case.execute(input)
    assert result.is_ok()

# Functional: End-to-end con BD real
async def test_use_case_e2e(uow_factory, dbsession):
    result = await use_case.execute(input)
    assert result.is_ok()
    # Verificar DB
```

### Step 5: Quality Gates (Antes de Commit)

```bash
# 1. Ruff: Linting y formatting
uv run ruff check --fix . && uv run ruff format .

# 2. mypy: Type checking (strict mode)
uv run mypy app

# 3. pytest: Todos los tests deben pasar
uv run pytest

# 4. Commit solo si TODO pasa
git add -A && git commit -m "..."
```

---

## 🎯 Key Patterns

### 1️⃣ Clean Architecture: Core → Infrastructure

**❌ MALO** (dependency pointing outward):

```python
# En app/core/usecases/event_usecases.py
from sqlalchemy.orm import Session  # ❌ Infrastructure dependency

class EnqueueEventUseCase:
    def __init__(self, session: Session):
        self.session = session  # Tight coupling!
```

**✅ BUENO** (dependency inversion):

```python
# En app/core/usecases/event_usecases.py
from app.core.unit_of_work import IUnitOfWork  # ✅ Abstract interface

class EnqueueEventUseCase:
    def __init__(self, uow: IUnitOfWork):
        self.uow = uow  # Loose coupling, testeable
```

### 2️⃣ Result Type para Manejo de Errores

**❌ MALO** (lanzar excepciones):

```python
async def execute(self, input: EnqueuedEventUseCaseInput) -> EnqueuedEventUseCaseOutput:
    if not input.name:
        raise ValidationError("name is required")  # ❌ Implicito
    # ...
```

**✅ BUENO** (Result type):

```python
async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[EnqueuedEventUseCaseOutput, ErrorDetail]:
    if not input.name:
        return Err(ErrorDetail(...))  # ✅ Explicito, type-safe
    # ...
```

### 3️⃣ UUID Auto-generation Pattern

**El patrón correcto** cuando se requiere auto-generación:

```python
# En Pydantic DTO: marcar que puede ser auto-generado
class EnqueuedEventUseCaseInput(BaseModel):
    id: UUID | None = Field(default_factory=uuid4)  # ✅ Default factory

# En Use Case: fallback explícito si es None
event_id = input.id if input.id is not None else uuid4()  # ✅ Explícito
evt = Event(id=event_id, ...)  # ✅ Contrato claro
```

### 4️⃣ Dependency Injection en Tests

**Unit Tests** (con mocks):

```python
@pytest.mark.asyncio
async def test_use_case_logic(uow_mock):
    # Fixture inyecta mock de UnitOfWork
    use_case = EnqueueEventUseCase(uow=uow_mock)
    result = await use_case.execute(input_data)

    assert result.is_ok()
    uow_mock.events.save_or_resolve_one.assert_called_once()
```

**Functional Tests** (BD real):

```python
@pytest.mark.asyncio
async def test_use_case_e2e(uow_factory):
    # Fixture inyecta factory que crea UnitOfWork con BD real
    async with uow_factory() as uow:
        use_case = EnqueueEventUseCase(uow=uow)
        result = await use_case.execute(input_data)
        # ...
```

### 5️⃣ Concurrency & Idempotence Patterns

**Scenario: 2 requests simultáneos con mismo external_uuid**

```python
# asyncio.gather() ejecuta en paralelo
results = await asyncio.gather(
    use_case.execute(input1),  # Same external_uuid
    use_case.execute(input2),  # Same external_uuid
)

# ✅ EXPECTED: Ambos retornan el MISMO evento (idempotente)
assert results[0].id == results[1].id
# ✅ DB contiene solo 1 registro
```

**Cómo funciona la idempotencia**:

1. Request 1 llega primero → Crea evento, guarda en BD
2. Request 2 llega casi simultáneamente → `save_or_resolve_one()` detecta external_uuid existente
3. Request 2 → Retorna el evento existente (mismo que Request 1)
4. ✅ Result: 1 evento en BD, 2 requests retornan idéntico

---

## 🧪 Testing Strategy

### Estructura: Unit vs Functional

| Aspecto          | Unit Tests                   | Functional Tests            |
| ---------------- | ---------------------------- | --------------------------- |
| **Ubicación**    | `tests/unit/`                | `tests/functional/`         |
| **Dependencias** | Mockeadas                    | Reales (BD en memoria)      |
| **Velocidad**    | ~100ms                       | ~500ms                      |
| **Objetivo**     | Lógica aislada               | End-to-end flows            |
| **BD**           | No necesaria                 | SQLite in-memory            |
| **Ejemplo**      | Validar UseCase con mock UoW | Validar UseCase con BD real |

### Commandos Útiles

```bash
# Ejecutar TODO
uv run pytest

# Solo unitarios
uv run pytest tests/unit/ -v

# Solo funcionales
uv run pytest tests/functional/ -v

# Test específico
uv run pytest tests/unit/test_enqueue_event_usecase_unit.py::test_u1_valid_input_new_event -v

# Con cobertura
uv run pytest --cov=app

# Modo watch (re-ejecuta al cambiar archivos)
uv run pytest -v --tb=short -x  # -x: stop on first failure
```

### Fixture Pattern para DI en Tests

**Crear mock de UnitOfWork** (en `tests/unit/conftest.py`):

```python
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def uow_mock() -> MagicMock:
    """Mock de UnitOfWork para unit tests"""
    mock = MagicMock(spec=UnitOfWork)
    mock.events = MagicMock()
    mock.events.save_or_resolve_one = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock
```

**Usar en test**:

```python
@pytest.mark.asyncio
async def test_something(uow_mock):
    uow_mock.events.save_or_resolve_one = AsyncMock(return_value=Ok([event]))

    use_case = EnqueueEventUseCase(uow=uow_mock)
    result = await use_case.execute(input)

    assert result.is_ok()
```

---

## ✨ Quality Standards

### 1. Ruff (Linting & Formatting)

**Obligatorio antes de commit/push:**

```bash
# Fix + Format + Check (en ese orden)
uv run ruff check --fix . && uv run ruff format . && uv run ruff check .
```

**Configuración** (`pyproject.toml`):

- Line length: 90 chars
- Target: Python 3.12
- Rules: E, W, F, I, B, C4, UP

**Lo que valida**:

- ✅ Imports ordenados (isort)
- ✅ Unused imports/variables removidos
- ✅ Type hints presentes
- ✅ Código formateado consistentemente
- ✅ Deprecated features actualizados

### 2. mypy (Type Checking - Strict Mode)

**Obligatorio antes de commit/push:**

```bash
uv run mypy app
```

**Configuración** (`pyproject.toml`):

- `strict = true` → Requiere types en TODO
- `disallow_untyped_defs = true` → Funciones sin tipos = error
- `disallow_incomplete_defs = true` → Types incompletos = error

**Impacto práctico**:

```python
# ❌ RECHAZADO por mypy
def process_data(input):  # Missing type hint
    return input.value

# ✅ ACEPTADO por mypy
def process_data(input: InputDTO) -> OutputDTO:
    return OutputDTO(value=input.value)
```

### 3. pytest (Testing)

**Objetivos**:

- ✅ Cobertura >= 75%
- ✅ Tests unitarios para lógica aislada
- ✅ Tests funcionales para flujos end-to-end
- ✅ Concurrency tests para race conditions

**Patrones**:

**Unit Test**:

```python
@pytest.mark.asyncio
async def test_u1_valid_input(uow_mock):
    """Test lógica aislada con mock"""
    use_case = EnqueueEventUseCase(uow=uow_mock)
    result = await use_case.execute(valid_input)
    assert result.is_ok()
```

**Functional Test**:

```python
@pytest.mark.asyncio
async def test_f1_happy_path(uow_factory, dbsession):
    """Test end-to-end con BD real"""
    async with uow_factory() as uow:
        use_case = EnqueueEventUseCase(uow=uow)
        result = await use_case.execute(valid_input)
        assert result.is_ok()

        # Verificar en DB
        db_event = await dbsession.get(Event, result.unwrap().id)
        assert db_event is not None
```

**Concurrency Test** (race conditions):

```python
@pytest.mark.asyncio
async def test_c1_concurrent_same_external_uuid(uow_factory):
    """Test 2 requests simultáneos con mismo external_uuid"""
    results = await asyncio.gather(
        make_request(uuid1),
        make_request(uuid1),  # ← Mismo external_uuid
    )

    # ✅ Ambos retornan el MISMO evento (idempotente)
    assert results[0]["id"] == results[1]["id"]
```

---

## 🔧 Common Commands

### Setup & Installation

```bash
# Instalar dependencias
uv sync --group dev

# Actualizar dependencias
uv sync --upgrade

# Lock archivo
uv lock
```

### Development

```bash
# Servidor con auto-reload
uv run fastapi dev

# Shell interactivo con contexto del proyecto
uv run python

# Ejecutar script específico
uv run python -c "import app; print(app.__name__)"
```

### Testing & Quality

```bash
# Todos los tests
uv run pytest

# Solo tests fallidos del último run
uv run pytest --lf

# Tests en modo watch (re-ejecuta al cambiar archivos)
uv run pytest -v --tb=short -k "test_name"

# Cobertura detallada
uv run pytest --cov=app --cov-report=html

# Linting
uv run ruff check . && uv run ruff format . && uv run mypy app

# Pre-commit (quando esté configurado)
git commit  # Automáticamente ejecuta checks
```

### Git & Commits

```bash
# Ver status
git status

# Commits
git add -A && git commit -m "feat(module): description"

# Conventional Commits:
feat(scope)   # Nueva funcionalidad
fix(scope)    # Bug fix
test(scope)   # Tests
docs(scope)   # Documentación
refactor()    # Refactorización (sin cambios funcionales)
```

---

## 🌍 Environment Configuration

### Multi-Environment System

```bash
# Development
ENV=development
DATABASE_URL=sqlite:///./var/lib/database.sqlite
LOG_LEVEL=DEBUG

# Testing
ENV=test
DATABASE_URL=sqlite:///:memory:
LOG_LEVEL=WARNING

# Production
ENV=production
DATABASE_URL=postgresql://user:password@host/db
LOG_LEVEL=INFO
```

**Ubicación**:

- `local.env` → Desarrollo (gitignored)
- `test.env` → Testing
- Variables de entorno del sistema → Producción

**Cómo se cargan** (en `app/core/settings.py`):

1. Leer variable `ENV`
2. Si `ENV=development` → cargar `local.env`
3. Si `ENV=test` → cargar `test.env`
4. Sino → usar variables de entorno del sistema

---

## 📚 Architecture Deep Dive

### Clean Architecture Layers

```
                    USE CASES
                  (Business Logic)
                        ↑
                    ENTITIES
                  (Domain Models)
                        ↑
REPOSITORIES     INTERFACES    GATEWAYS
(Abstractions)   (Contracts)   (Adapters)
       ↑               ↑              ↑
INFRASTRUCTURE (SQLAlchemy, FastAPI, Redis, etc.)
```

**En nuestro proyecto**:

- `app/core/entities.py` → ENTITIES
- `app/core/repositories.py`, `app/core/repository_event.py` → INTERFACES (ABC)
- `app/core/usecases/` → USE CASES
- `app/infrastructure/` → INFRASTRUCTURE

**Regla de Dependencias**: Las dependencias fluyen HACIA ADENTRO, nunca hacia afuera.

### Repository Pattern

```python
# Interface (app/core/repository_event.py)
class EventRepository(ABC):
    @abstractmethod
    async def save(self, entity: Event) -> Result[Event, ErrorDetail]:
        pass

    @abstractmethod
    async def get_by_id(self, id: UUID) -> Result[Event, ErrorDetail]:
        pass

# Implementation (app/infrastructure/db/repository_event.py)
class AsyncSQLAlchemyEventRepository(EventRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, event: Event) -> Result[Event, ErrorDetail]:
        self.session.add(event)
        await self.session.flush()
        return Ok(event)
```

### Unit of Work Pattern

```python
# Abstraction (app/core/unit_of_work.py)
class UnitOfWork(ABC):
    @property
    @abstractmethod
    def courses(self) -> CourseRepository:
        pass

    @property
    @abstractmethod
    def events(self) -> EventRepository:
        pass

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        pass

    @abstractmethod
    async def commit(self):
        pass

# Implementation (app/infrastructure/db/unit_of_work.py)
class AsyncSQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory):
        self.session = None
        self._session_factory = session_factory

    async def __aenter__(self):
        self.session = self._session_factory()
        self.events = AsyncSQLAlchemyEventRepository(self.session)
        return self

    async def commit(self):
        await self.session.commit()
```

**Uso en Use Cases**:

```python
async def execute(self, input: Input) -> Result[Output, Error]:
    async with self.uow as uow:
        # Usar repositorios a través de UoW
        result = await uow.events.save(event)
        await uow.commit()  # Transacción atómica
        return result
```

---

## 🎯 Principio: "Lo que no está, no falla"

Este principio guía fundamental busca mantener el codebase minimalista, mantenible y libre de código muerto.

### Por qué es importante

- **Menos bugs**: Código no usado no puede fallar en producción
- **Mantenibilidad**: Menos código = menos que entender, probar y mantener
- **Claridad**: Elimina confusión sobre qué código está activo
- **Performance**: Sin overhead de código nunca ejecutado
- **Coverage real**: Métricas de cobertura más significativas

### Cómo aplicarlo

#### 1. **Antes de agregar código, preguntarse:**

- ¿Este código se usa ahora, no "podría usarse después"?
- ¿Existe un requerimiento específico que justifique su existencia?
- ¿Hay tests que demuestren su uso?

#### 2. **Durante code reviews:**

```python
# ❌ MALO: Métodos "por si acaso"
class EventRepository:
    async def get_by_name(self, name: str):  # Nunca usado
        pass

    async def get_by_date_range(self, start, end):  # Nunca usado
        pass

    async def get_by_id(self, id: UUID):  # ✅ Usado
        pass

# ✅ BUENO: Solo métodos requeridos
class EventRepository:
    async def get_by_id(self, id: UUID):  # ✅ Usado por UseCases
        pass
```

#### 3. **Refactoring agresivo:**

```python
# ANTES: Helpers privados no usados
class AsyncSQLAlchemyEventRepository:
    async def _resolve_existing_event(self, event):  # ❌ Nunca llamado
        ...

    async def _select_event_by_id(self, id):  # ❌ Nunca llamado
        ...

    async def _coerce_to_event(self, found):  # ❌ Nunca llamado
        ...

    async def save(self, event):  # ✅ Usado
        ...

# DESPUÉS: Solo helpers utilizados
class AsyncSQLAlchemyEventRepository:
    async def _ensure_transitions_collection(self, event):  # ✅ Usado en save
        ...

    async def save(self, event):  # ✅ Usado
        self._ensure_transitions_collection(event)
        ...
```

#### 4. **Detectar código muerto:**

```bash
# Usar grep para buscar referencias
grep -r "nombre_funcion" app/ tests/

# Si solo aparece en definición → código muerto
# Ejemplo real de este proyecto (~80 líneas eliminadas):
# - _resolve_existing_event: 0 usos
# - _select_event_by_external_uuid: 0 usos
# - _select_event_by_id: 0 usos
# - _coerce_to_event: 0 usos
```

#### 5. **Interfaces limpias:**

```python
# ❌ MALO: Interfaz con métodos no implementados
class EventRepository(ABC):
    @abstractmethod
    async def archive(self, event): pass  # Nunca implementado

    @abstractmethod
    async def restore(self, event): pass  # Nunca implementado

# ✅ BUENO: Solo contratos realmente necesarios
class EventRepository(ABC):
    @abstractmethod
    async def delete(self, event): pass  # Implementado y usado

    @abstractmethod
    async def save(self, event): pass  # Implementado y usado
```

### Red flags (señales de código a eliminar)

- ❌ Función sin tests → Probablemente no usada
- ❌ Método privado sin llamadas internas → Código muerto
- ❌ Parámetro nunca accedido → Sobrecarga innecesaria
- ❌ Comentario "TODO: Usar esto después" > 1 mes → No se necesita
- ❌ Import nunca usado → Ruff lo detecta automáticamente
- ❌ Clase con coverage 0% → Revisar si es necesaria

### Métricas de éxito

- **Coverage aumenta** al eliminar código muerto (0% coverage)
- **Menos líneas de código** para misma funcionalidad
- **Tests más enfocados** en código que realmente importa
- **Code reviews más rápidos** al haber menos qué revisar

### Ejemplo real de este proyecto

**Commit**: `refactor(repository): clean up AsyncSQLAlchemyEventRepository`

- ❌ Eliminados: 4 métodos privados (~80 líneas) nunca usados
- ✅ Resultado: Coverage subió de 78% a 87% (+9%)
- ✅ Beneficio: Código más claro sin sobrecarga

---

## 🐛 Troubleshooting

### Problema: Tests fallan con `ModuleNotFoundError`

```bash
# Solución: Verificar pythonpath en pyproject.toml
[tool.pytest.ini_options]
pythonpath = ["."]  # ← Debe estar presente

# Ejecutar desde raíz de mcpserver
cd /path/to/mcpserver
uv run pytest
```

### Problema: `mypy` reporta errores inesperados

```bash
# Ver errores con códigos
uv run mypy app --show-error-codes

# Solución típica: Falta type hint
# ❌ def process(self, data):
# ✅ def process(self, data: InputDTO) -> OutputDTO:
```

### Problema: `Ruff` reporta imports no utilizados

```bash
# Auto-fix
uv run ruff check --fix .

# Si persiste, revisar imports
grep -n "^from\|^import" archivo.py
```

### Problema: Tests timeout en funcionales

```bash
# Aumentar timeout
pytest --timeout=30  # 30 segundos

# O usar en el test
@pytest.mark.timeout(30)
async def test_something():
    ...
```

---

## 📖 Workflow Típico (Ejemplo Real)

Supongamos que quieres implementar una feature: "Crear endpoint para filtrar eventos por estado"

### 1. Requerimientos

```
- Endpoint GET /events?state=PENDING
- Retornar lista de eventos con ese estado
- Validar que state es un valor válido
- Paginación opcional (limit, offset)
```

### 2. Diseño

```
# Entidad: Already defined in entities.py (EventState enum exists)

# DTO Input
class FilterEventsInput(BaseModel):
    state: EventState
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

# DTO Output
class FilterEventsOutput(BaseModel):
    events: list[EventDTO]
    total: int
    limit: int
    offset: int

# Interface en repository
async def get_many_by_state(
    self, state: EventState, limit: int, offset: int
) -> list[Event]:
    pass
```

### 3. Implementar

```python
# 1. En app/core/usecases/event_usecases.py
class FilterEventsByStateUseCase(AsyncUseCase[FilterEventsInput, FilterEventsOutput]):
    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def execute(self, input: FilterEventsInput) -> Result[FilterEventsOutput, Error]:
        async with self.uow:
            events = await self.uow.events.get_many_by_state(
                state=input.state,
                limit=input.limit,
                offset=input.offset,
            )
            return Ok(FilterEventsOutput(
                events=[EventDTO.from_entity(e) for e in events],
                total=len(events),
                limit=input.limit,
                offset=input.offset,
            ))

# 2. En app/infrastructure/db/repository_event.py
async def get_many_by_state(
    self, state: EventState, limit: int, offset: int
) -> list[Event]:
    stmt = (
        select(Event)
        .where(Event.state == state)
        .limit(limit)
        .offset(offset)
    )
    result = await self.session.execute(stmt)
    return result.scalars().all()

# 3. En app/infrastructure/api/routes.py
@router.get("/events")
async def filter_events(
    state: EventState,
    limit: int = 10,
    offset: int = 0,
    use_case: FilterEventsByStateUseCase = Depends(),
) -> dict:
    input_data = FilterEventsInput(state=state, limit=limit, offset=offset)
    result = await use_case.execute(input_data)
    if result.is_err():
        raise result.unwrap_err()
    return result.unwrap().model_dump()
```

### 4. Testing

```python
# tests/unit/test_filter_events_unit.py
@pytest.mark.asyncio
async def test_filter_by_state(uow_mock):
    """Unit: Lógica aislada"""
    uow_mock.events.get_many_by_state = AsyncMock(
        return_value=[event1, event2]
    )

    use_case = FilterEventsByStateUseCase(uow=uow_mock)
    input_data = FilterEventsInput(state=EventState.PENDING)
    result = await use_case.execute(input_data)

    assert result.is_ok()
    assert len(result.unwrap().events) == 2

# tests/functional/test_filter_events_functional.py
@pytest.mark.asyncio
async def test_filter_by_state_e2e(uow_factory, dbsession):
    """Functional: End-to-end con BD real"""
    # Setup: Crear eventos con diferentes estados
    event1 = Event(name="E1", state=EventState.PENDING, ...)
    event2 = Event(name="E2", state=EventState.PENDING, ...)
    event3 = Event(name="E3", state=EventState.COMPLETED, ...)
    dbsession.add_all([event1, event2, event3])
    await dbsession.commit()

    # Test
    async with uow_factory() as uow:
        use_case = FilterEventsByStateUseCase(uow=uow)
        result = await use_case.execute(
            FilterEventsInput(state=EventState.PENDING)
        )

    # Assert
    assert result.is_ok()
    output = result.unwrap()
    assert output.total == 2
    assert all(e.state == EventState.PENDING for e in output.events)
```

### 5. Quality Gates

```bash
# Linting
uv run ruff check --fix . && uv run ruff format .

# Type checking
uv run mypy app

# Tests
uv run pytest

# Si TODO pasa:
git add -A
git commit -m "feat(events): add filter by state endpoint with unit+functional tests"
git push
```

---

## 🔐 Common Pitfalls & How to Avoid

| Pitfall                           | Síntoma                                 | Solución                                                                  |
| --------------------------------- | --------------------------------------- | ------------------------------------------------------------------------- |
| **No inyectar dependencias**      | Tests imposibles de mockear             | Siempre pasar dependencias al `__init__`, nunca instanciar internamente   |
| **Imports en app/ desde testing** | `unittest.mock` importado en producción | NUNCA importar testing libs en `app/`. Usar mocks solo en `tests/`        |
| **Type hints incompletos**        | mypy falla                              | Especificar tipos explícitos en TODAS las funciones públicas              |
| **Tests flaky (aleatorios)**      | Tests fallan a veces                    | Evitar `time.sleep()`, usar fixtures determinísticas                      |
| **BD no limpias entre tests**     | Tests interfieren entre sí              | Usar fixture de BD en memoria que se reinicia cada test                   |
| **Coverage drops**                | Métodos nuevos sin tests                | Escribir tests ANTES de mergear (o al menos junto con código)             |
| **Código muerto acumulado**       | Coverage bajo, código sin tests         | Aplicar "lo que no está no falla": eliminar código no usado agresivamente |

---

## 📊 Current Status

### Tests Coverage

- ✅ **60 tests passing** (58 unit + functional, 2 skipped)
- ✅ **87% coverage** (target: ≥75%)
- ✅ Unit tests: 41 tests
- ✅ Functional tests: 17 tests
- ✅ Concurrency tests: 3 tests (C1: external_uuid, C2: internal id, C3: mixed)

### Code Quality

- ✅ **Ruff**: ALL PASSED
- ✅ **mypy**: strict mode (green). Nota: `app/infrastructure/scrapy_spider/**` excluida temporalmente del análisis hasta su reimplementación.
- ✅ **Pre-commit hooks**: [Pendiente de implementar]

### Architecture

- ✅ Clean Architecture (3 capas)
- ✅ Dependency Injection (todos los componentes)
- ✅ Repository Pattern
- ✅ Unit of Work Pattern
- ✅ Result Type (error handling)

---

## 📚 Key Takeaways for Developers

1. **Entidad-Repositorio-UseCase**: Este es el patrón repetible. Cada nueva feature sigue estos pasos.

2. **Dependency Injection es NO NEGOCIABLE**: Sin DI, no hay testing. Con DI, todo es testeable.

3. **Types Primero**: mypy strict mode obliga a ser explícito. Esto reduce bugs.

4. **Tests = Documentación**: Un buen test describe cómo usar la funcionalidad. Leerlos para entender el proyecto.

5. **"Lo que no está, no falla"**: Eliminar código muerto agresivamente. Solo mantener lo esencial y utilizado.

6. **Concurrency es Explícito**: `asyncio.gather()` + `save_or_resolve_one()` = Idempotencia garantizada.

7. **Quality Gates Antes de Commit**: Ruff + mypy + pytest. Sin pasar estos, no mergear.

---

## 🎓 Next Steps for Learning

1. **Leer**: [tests/unit/test_enqueue_event_usecase_unit.py](tests/unit/test_enqueue_event_usecase_unit.py) - Entender mocking
2. **Leer**: [tests/functional/test_enqueue_event_concurrency_c1_c2.py](tests/functional/test_enqueue_event_concurrency_c1_c2.py) - Entender concurrency
3. **Leer**: [app/core/usecases/event_usecases.py](app/core/usecases/event_usecases.py) - Entender UseCase structure
4. **Implementar**: Nueva feature (ej: Transiciones de estado) siguiendo workflow descrito

---

## 📞 Getting Help

### Para Agentes IA:

Si estás implementando una feature:

1. Consulta este documento → Busca el **Workflow Típico** más similar a tu tarea
2. Sigue los steps: Requerimientos → Diseño → Implementar → Testing → Quality Gates
3. Si hay duda sobre patrón → Ve a **Key Patterns** section
4. Si hay error → Ve a **Troubleshooting** section

### Para Desarrolladores Humanos:

1. Empieza con **Quick Start** (Setup inicial)
2. Lee **Project Overview** (Entender estructura)
3. Consulta **Development Workflow** para cada feature
4. Usa **Common Commands** para operaciones diarias
5. Bookmark los **Key Patterns** - los necesitarás constantemente

---

## 📝 Document Versioning

| Versión | Fecha      | Cambios                                                                                                                                                                                            |
| ------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v2.1    | 2025-12-28 | **Added "Lo que no está, no falla" principle**: Agregado como principio core con sección dedicada, ejemplos prácticos, red flags y métricas de éxito. Incluido en Common Pitfalls y Key Takeaways. |
| v2.0    | 2025-12-27 | **Complete rewrite**: Reorganizado para ser más práctico y repetible. Added concurrency patterns, simplified commands, added typical workflow example. Agregados principios SOLID explícitamente.  |
| v1.0    | 2024-12-10 | Versión inicial                                                                                                                                                                                    |

---

**Última actualización**: 2025-12-28
**Próxima revisión**: Después de implementar C3 (mixed concurrency scenarios)
