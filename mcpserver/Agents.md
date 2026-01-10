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

## 📚 Referencias de Diseño (Histórico)

- [PHASE4_COMPLETION_SUMMARY.md](PHASE4_COMPLETION_SUMMARY.md)
- [PROCESS_EVENT_USECASE2_REFACTORING.md](PROCESS_EVENT_USECASE2_REFACTORING.md)
- [QUALITY_ANALYSIS_NEO_EVENT_USECASE.md](QUALITY_ANALYSIS_NEO_EVENT_USECASE.md)
- [PROJECT_COMPLETION_SUMMARY.md](PROJECT_COMPLETION_SUMMARY.md)
- [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
- [COVERAGE_OPPORTUNITIES.md](COVERAGE_OPPORTUNITIES.md)
- [ARCHITECTURE_OPPORTUNITIES.md](ARCHITECTURE_OPPORTUNITIES.md)
- [ANALYSIS_ENQUEUE_EVENT_USECASE.md](ANALYSIS_ENQUEUE_EVENT_USECASE.md)

> Nota: estos archivos viven en la raíz de `mcpserver/` y se mantienen como histórico. Para nuevas definiciones, preferir `mcpserver/docs/` y diagramas en Mermaid.

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

Esta sección recoge el workflow optimizado para iteraciones rápidas entre desarrolladores y agentes IA, orientado a producir cambios pequeños, verificables y reversibles.

Principios clave

- Iteraciones cortas: objetivo claro + tests que validan aceptación.
- Core antes de infra: implementar lógica de dominio y cubrirla con unit tests antes de tocar infra.
- Atomicidad explícita: TX1 (lock) y TX2 (outcome) separadas y comprobadas por tests E2E.

Workflow recomendado (pasos mínimos por iteración)

1. Objetivo y criterios (1–3 líneas): listar resultados esperados y los tests que demostrarán éxito.
2. Diseñar contrato del core (UseCase/Entity): inputs/outputs y estados críticos.
3. Implementar core + unit tests (cobertura de ramas críticas). Ejecutar solo estos tests hasta verde.
4. Añadir 1 test funcional crítico (E2E) que valide transacciones, idempotencia o side-effects.
5. Ejecutar suite completa, revisar fallos y cobertura; priorizar crear tests en módulos con baja cobertura.
6. Documentar cambios relevantes (breve nota en `Agents.md` o `docs/`) y crear PR pequeño.

Checklist rápido (usar como pre-PR)

- [ ] Objetivo y criterios definidos
- [ ] Unit tests para el core (rutas felices + errores esperados)
- [ ] Unit tests verdes localmente
- [ ] 1 test funcional crítico agregado
- [ ] Suite completa verde y cobertura aceptable (team/CI gate)
- [ ] Documentación mínima actualizada

Prácticas operativas para maximizar éxito con agentes IA

- Siempre pedir al agente que devuelva una lista corta de cambios (todo list) antes de aplicar parches.
- El agente debe ejecutar tests relevantes tras cada cambio y reportar resultados concisos (passed/failed + cobertura parcial).
- Para E2E DB: persistir con `save_or_resolve_one` o recuperar la fila canónica (`getOne`) antes de pasar entidades al UseCase para evitar IntegrityError por objetos detachados.
- Si un UseCase hace TX1 (lock), el processor que verifica la persistencia debe leer desde otra sesión (simula consumidor externo).
- Preferir `merge()`/`session.merge()` en helpers de repositorio cuando tests manipulan instancias detachadas.

Estrategia de testing y cobertura

- Priorizar tests unitarios en módulos core (`app/core/usecases/*`) y en repositorios (`app/infrastructure/db/*`).
- Cuando la cobertura global falla en CI, identificar top-5 módulos con menor coverage y añadir tests focalizados.

Comunicación y commits

- Commits pequeños y atómicos: cada cambio debe poder revertirse sin afectar otras piezas.
- Añadir mensajes de commit con referencia a tests agregados (ej: "test(event_usecase): add validate_and_lock unit tests").

Referencias rápidas

- Guía ampliada con ejemplos y checklist: `docs/AGENT_ITERATION_GUIDE.md` (añadida al repo).

### Prompt Templates & TODOs (Ejemplos rápidos)

Usar estas plantillas cuando pidas trabajo al agente para maximizar claridad y velocidad:

- **Implementación puntual** (mínimo, verificable):

  > "Implementar `validate_and_lock` en `ProcessEventIdealUseCase`.
  > Objetivo: PENDING→PROCESSING persistido (TX1).
  > Tests: `test_pending_transitions_to_processing`.
  > Restricciones: no tocar infra ni handlers."

- **Bugfix reproducible**:

  > "Fix IntegrityError en E2E (test_process_event_tx_transactions). Contexto: conflicto por instancia detachada. Reproducir con test, parche minimal usando `session.merge()` o `save_or_resolve_one`, añadir test que falle antes del fix."

- **Refactor + cobertura**:

  > "Refactor `save_or_resolve_one` para usar `merge()` y añadir unit tests que cubran comportamiento en conflicto por `external_uuid`. Mantener API pública estable."

Plantilla de TODO (usar en PR o en el prompt al agente):

```
TODO:
- [ ] Objetivo (1–2 líneas): <describir>
- [ ] Tests unitarios añadidos: <lista de tests>
- [ ] Tests funcionales añadidos (E2E críticos): <lista de tests>
- [ ] Lint + mypy pasados
- [ ] Commit y descripción clara
```

Uso: pegar la plantilla en la descripción del PR o en la petición al agente para asegurar entregas verificables.

### Step 3: Implementación (Core primero)

Implementar las 4 etapas en **app/core/usecases/neo_event_usecase.py**:

#### Etapa 0: Fetch Event (orchestration start)

```python
async def execute(self, event_id: UUID) -> Result[ProcessEventResult, ErrorDetail]:
    # Obtener evento por ID
    result = await self.uow.events.getOne(event_id)
    if result.is_err():
        return result  # Short-circuit: fetch error

    event = result.unwrap()
    # Continuar con stages 1-3
    ...
```

#### Etapa 1: Validate & Lock (TX1)

```python
async def validate_and_lock(self, event: Event) -> Result[Event, ErrorDetail]:
    # Validar que estado sea PENDING | TEMPORAL_ERROR | RETRYING
    # Inicializar ProcessingContext tipado
    # Transicionar estado: PENDING→PROCESSING, TEMPORAL_ERROR→RETRYING
    # [TX1] uow.events.save(event) + uow.commit()
    # Retornar Ok(event) o Err(ErrorDetail)
```

**Validaciones**:

- `event.state` en [PENDING, TEMPORAL_ERROR, RETRYING]
- Si no, retornar Err (sin persistir)

**Transiciones**:

- PENDING → PROCESSING
- TEMPORAL_ERROR → RETRYING
- RETRYING → RETRYING (sin cambio)

#### Etapa 2: Process with Retries (sin persistencia)

```python
async def process_with_retries(self, event: Event) -> Result[Event, ErrorDetail]:
    # Obtener procesador del registry
    processor = processor_registry.get(event.processor_type, NoOpProcessor())

    # tenacity.AsyncRetrying: max 3 intentos, exponential backoff 0.1-2s
    # En cada intento: classify_error (TRANSIENT vs PERMANENT)
    # TRANSIENT: reintenta
    # PERMANENT: retorna Err inmediatamente (sin persístir)

    # Actualizar event.attempt_count, event.last_activity, event.pending_callback
    # Retornar Ok(event) o Err (sin persistencia)
```

**Retry Timeline**:

- Intento 1: 0ms (immediate)
- Intento 2: 100ms
- Intento 3: 500ms
- p95 = 600ms

**Error Classification**:

- PERMANENT (4xx HTTP, ValueError) → Fail immediately
- TRANSIENT (5xx HTTP, timeouts) → Retry

#### Etapa 3: Persist Outcome (TX2)

```python
async def persist_outcome(self, event: Event) -> Result[Event, ErrorDetail]:
    # 4 caminos según evento.resultado:

    # 1. SUCCESS → PROCESSING/RETRYING→COMPLETED
    if event_success:
        event.state = EventState.COMPLETED

    # 2. PENDING_CALLBACK → solo guardar context, no cambiar state
    if event.pending_callback:
        event.processing_context = {...}

    # 3. FAILED → evento.state = PROCESSING→FAILED
    if event_failed and event.from_state == PROCESSING:
        event.state = EventState.FAILED

    # 4. RETRY_EXHAUSTED → evento.state = RETRYING→EXHAUSTED
    if event.retry_exhausted and event.from_state == RETRYING:
        event.state = EventState.EXHAUSTED

    # [TX2] uow.events.save(event) + uow.commit()
    # Retornar Ok(event) o Err
```

#### Etapa 4: Execute (Orquestación)

```python
async def execute(self, event_id: UUID) -> Result[ProcessEventResult, ErrorDetail]:
    # Patrón: Pattern Matching (async-safe, NO and_then)

    # 0. Fetch
    result = await self.uow.events.getOne(event_id)
    if isinstance(result, Err):
        return result
    event = result.unwrap()

    # 1. Validate & Lock
    result = await self.validate_and_lock(event)
    if isinstance(result, Err):
        return result
    event = result.unwrap()

    # 2. Process with Retries
    result = await self.process_with_retries(event)
    if isinstance(result, Err):
        return result
    event = result.unwrap()

    # 3. Persist Outcome
    result = await self.persist_outcome(event)
    if isinstance(result, Err):
        return result
    event = result.unwrap()

    # 4. Retornar DTO (no entity)
    return Ok(ProcessEventResult(event=event, ...))
```

### Step 4: Testing (Unit + Functional según necesidad)

**Estrategia de Testing para ProcessEventIdealUseCase**:

#### Test Unitarios (Mocks de UoW)

```python
# tests/unit/test_process_event_ideal_validate_lock.py
@pytest.mark.asyncio
async def test_pending_transitions_to_processing(uow_mock):
    """Stage 1: PENDING→PROCESSING con TX1"""
    event = make_event(state=EventState.PENDING)
    uow_mock.events.save_or_resolve_one = AsyncMock(return_value=Ok([event]))

    use_case = ProcessEventIdealUseCase(uow=uow_mock)
    result = await use_case.validate_and_lock(event)

    assert result.is_ok()
    assert result.unwrap().state == EventState.PROCESSING
    uow_mock.commit.assert_called_once()

# tests/unit/test_process_event_ideal_process_with_retries.py
@pytest.mark.asyncio
async def test_processor_success_returns_event(uow_mock, processor_mock):
    """Stage 2: Procesador exitoso"""
    event = make_event(state=EventState.PROCESSING)
    processor_mock.process = AsyncMock(return_value=Ok({"status": 200}))

    use_case = ProcessEventIdealUseCase(uow=uow_mock, processor_registry={"test": processor_mock})
    result = await use_case.process_with_retries(event)

    assert result.is_ok()

# tests/unit/test_process_event_ideal_persist_outcome.py
@pytest.mark.asyncio
async def test_success_transitions_to_completed(uow_mock):
    """Stage 3: SUCCESS→COMPLETED con TX2"""
    event = make_event(state=EventState.PROCESSING, result_data={"status": 200})

    use_case = ProcessEventIdealUseCase(uow=uow_mock)
    result = await use_case.persist_outcome(event)

    assert result.is_ok()
    assert result.unwrap().state == EventState.COMPLETED

# tests/unit/test_process_event_ideal_execute_orchestration.py
@pytest.mark.asyncio
async def test_execute_happy_path_pending_to_completed(uow_mock, processor_mock):
    """Stage 4: Orquestación PENDING→PROCESSING→COMPLETED"""
    event = make_event(state=EventState.PENDING)
    uow_mock.events.getOne = AsyncMock(return_value=Ok(event))

    use_case = ProcessEventIdealUseCase(uow=uow_mock, processor_registry={"test": processor_mock})
    result = await use_case.execute(event.id)

    assert result.is_ok()
    assert result.unwrap().state == EventState.COMPLETED
```

**Cobertura de Gaps** (11 tests adicionales para branches no cubiertos):

- `metadata=None` en ProcessingContext
- `error=None` en exception handling
- Exception desde etapa RETRYING
- Errores de save en TX1 y TX2
- Resultados sin transición

#### Test Funcionales (BD real en memoria)

```python
# tests/functional/test_process_event_ideal_e2e.py
@pytest.mark.asyncio
async def test_happy_path_with_real_db(uow_factory):
    """E2E: Verificar persistencia en BD real"""
    async with uow_factory() as uow:
        # 1. Enqueue evento
        event = Event(id=uuid4(), name="test", state=EventState.PENDING, ...)
        uow.events.save(event)
        await uow.commit()

        # 2. Process
        use_case = ProcessEventIdealUseCase(uow=uow)
        result = await use_case.execute(event.id)

        # 3. Verificar BD
        assert result.is_ok()
        db_event = await uow.events.getOne(event.id)
        assert db_event.unwrap().state == EventState.COMPLETED
```

**Comandos útiles**:

```bash
# Unit aislado (SRP: cada etapa por separado)
uv run pytest tests/unit/test_process_event_ideal_validate_lock.py -v

# Todos los tests del módulo neo_event_usecase
uv run pytest tests/unit/ -k "ideal" -v

# Con cobertura
uv run pytest tests/unit/ -k "ideal" --cov=app/core/usecases/neo_event_usecase

# Test específico
uv run pytest tests/unit/test_process_event_ideal_execute_orchestration.py::test_execute_happy_path_pending_to_completed -v
```

### Step 5: Quality Gates (Antes de Commit)

```bash
# 1. Ruff: Linting y formatting
uv run ruff check --fix . && uv run ruff format .

# 2. mypy: Type checking (strict mode)
uv run mypy app

# 3. pytest: Suite completa o por módulo
uv run pytest

# 4. Commit solo si TODO pasa
git add -A && git commit -m "feat(usecase): stage1 validate_and_lock + unit tests"
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

### 6️⃣ Handler-Managed Transaction Orchestration (NEW - FASE 1-4)

**Patrón**: Handler (infrastructure) abre transacción, UseCase (core) ejecuta sin contexto.

**Beneficios**:

- Atomicidad: save + publish = 1 transacción
- Composición: 2+ use cases en 1 transacción
- Testabilidad: use cases sin context manager
- Arquitectura: Clean separation (handler orquesta, usecase ejecuta)

**Implementación**:

```python
# ❌ ANTES (UseCase abre contexto)
class EnqueueEventUseCase:
    async def execute(self, input):
        async with self.uow:  # ❌ UseCase manages TX
            return save(input)

# ✅ DESPUÉS (Handler abre contexto)
class EnqueueEventUseCase:
    async def execute(self, input):
        # ✅ NO context manager
        # ✅ Caller (handler) manages TX
        return save(input)

# Handler orchestrates
@EventSubscriber
async def handle_enqueue_event(event, msg, session=Depends(get_session)):
    try:
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            # Handler opens context
            usecase = EnqueueEventUseCase(uow)
            result = await usecase.execute(event)

            if result.is_ok():
                # Publish within SAME transaction
                await broker.publish({...}, stream="processing-event-subject")
                await msg.ack()
            else:
                await msg.nack()
        # Transaction commits here
    except Exception:
        await msg.nack()
```

**Cuando usar**:

- ✅ Handlers/Workers (orchestrate use cases)
- ✅ Multiple use cases en single operation
- ✅ Atomic save + publish patterns
- ❌ NOT para standalone use cases

**Más información**: [docs/TRANSACTION_PATTERN.md](docs/TRANSACTION_PATTERN.md)

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

**⚠️ DIRECTIVA CRÍTICA: Mock Solo Métodos Declarados en Interfaces**

**REGLA ABSOLUTA**: Los tests **SOLO** pueden mockear métodos que existen en las interfaces ABC (abstract base classes). Mockear métodos inexistentes es una **FALLA GRAVE** que invalida los tests.

**❌ PROHIBIDO**:

```python
# ❌ get_by_id() NO existe en EventRepository interface
uow_mock.events.get_by_id = AsyncMock(return_value=event)
```

**✅ CORRECTO**:

```python
# ✅ getOne() SÍ existe en EventRepository interface
from result import Ok
uow_mock.events.getOne = AsyncMock(return_value=Ok(event))
```

**Por qué es crítico**:

1. Los tests deben validar código que se ejecuta en runtime
2. Mockear métodos inexistentes eleva cobertura SIN validar requerimientos
3. Genera falsa sensación de seguridad
4. Los errores solo aparecen en producción

**Validación antes de mockear**:

```bash
# Siempre verificar que el método existe en la interfaz
grep -n "async def nombre_metodo" app/core/repository*.py
```

**Crear mock de UnitOfWork** (en `tests/unit/conftest.py`):

```python
from unittest.mock import AsyncMock, MagicMock
from result import Ok

@pytest.fixture
def uow_mock() -> MagicMock:
    """Mock de UnitOfWork para unit tests"""
    mock = MagicMock(spec=UnitOfWork)
    mock.events = MagicMock()
    # ✅ Solo mockear métodos que existen en EventRepository interface
    mock.events.save_or_resolve_one = AsyncMock()
    mock.events.getOne = AsyncMock()  # ✅ Existe en interface
    mock.events.getMany = AsyncMock()  # ✅ Existe en interface
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock
```

**Usar en test**:

```python
@pytest.mark.asyncio
async def test_something(uow_mock):
    # ✅ Mock retorna Result type como la interfaz define
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

- ✅ Cobertura mínima: >= 85% (gate de cobertura)
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

# Validar gate mínimo (85%) con toda la suite
uv run pytest -q

# Ejecutar un test aislado SIN cobertura (evita fallar por umbral al no medir todo)
uv run pytest -q --no-cov tests/functional/test_enqueue_event_concurrency_c1_c2.py::test_c2_concurrent_same_internal_id

# Ejecutar un test aislado deshabilitando addopts (by-pass global)
uv run pytest -q -o addopts="" tests/functional/test_enqueue_event_concurrency_c1_c2.py::test_c2_concurrent_same_internal_id

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
    async def getOne(self, id: UUID) -> Result[Event, ErrorDetail]:
        """Retrieves an event by its ID. Returns Result[Event, ErrorDetail]."""
        pass

# Implementation (app/infrastructure/db/repository_event.py)
class AsyncSQLAlchemyEventRepository(EventRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, event: Event) -> Result[Event, ErrorDetail]:
        self.session.add(event)
        await self.session.flush()
        return Ok(event)

    async def getOne(self, id: UUID) -> Result[Event, ErrorDetail]:
        result = await self.getMany([id])
        if result.is_err():
            return result
        events = result.unwrap()
        if len(events) == 0:
            return Err(ErrorDetail(error=ErrorCatalog.NOT_FOUND, detail=f"Event {id} not found"))
        return Ok(events[0])
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

    async def getOne(self, id: UUID):  # ✅ Usado
        pass

# ✅ BUENO: Solo métodos requeridos
class EventRepository:
    async def getOne(self, id: UUID):  # ✅ Usado por UseCases
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

---

## 🎯 Processor Pattern Architecture (PHASES 5-6)

El **Processor Pattern** es el mecanismo central que procesa eventos de forma extensible. Cada tipo de evento puede tener un procesador especializado.

### 4+ Processor Types

```
┌─────────────────────────────────────────────────────┐
│                    Event Processing                 │
└─────────────────────────────────────────────────────┘
                           ↓
        ┌──────────────────┬──────────────────┐
        ↓                  ↓                  ↓
  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
  │   Sync       │ │   Async      │ │    NoOp      │
  │  Processors  │ │  Processors  │ │  Processor   │
  └──────────────┘ └──────────────┘ └──────────────┘
        ↓                  ↓                ↓
  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
  │ ApiCall      │ │ LongRunning  │ │  Fallback    │
  │ (HTTP async) │ │ (Callback)   │ │ (unregistered│
  └──────────────┘ └──────────────┘ │  events)     │
  ┌──────────────┐                  └──────────────┘
  │ Grpc         │
  │ (gRPC async) │
  └──────────────┘
  ┌──────────────┐
  │ LocalUseCase │
  │ (local mthds)│
  └──────────────┘
```

### Sync Processors Implementation

**Ubicación**: [app/infrastructure/processors/sync_processors.py](app/infrastructure/processors/sync_processors.py)

#### 1️⃣ ApiCallProcessor (HTTP Async)

```python
class ApiCallProcessor(IProcessor):
    """Procesa eventos realizando llamadas HTTP a APIs externas"""

    async def process(self, event: Event) -> Result[dict, ErrorType]:
        # Config: 5 intentos max, retry = 2x100ms rápido + exponencial
        # 2x100ms = 200ms rápido
        # Luego: 500ms, 1000ms, 2000ms exponencial
        # p95 total = 1700ms (UX-optimizado)

        # Error classification:
        # - 4xx errors → PERMANENT (no retry)
        # - 5xx errors → TRANSIENT (retry)
        # - Connection errors → TRANSIENT
```

**Retry Timeline**:

- Attempt 1: 0ms (immediate)
- Attempt 2: 100ms
- Attempt 3: 100ms + 500ms = 600ms
- Attempt 4: 100ms + 500ms + 1000ms = 1600ms
- Attempt 5: 100ms + 500ms + 1000ms + 2000ms = 3600ms
- **p95 = 1700ms** (ajustado para UX)

**Casos de uso**: Webhooks, llamadas a APIs externas, microservicios HTTP

#### 2️⃣ GrpcProcessor (gRPC Async)

```python
class GrpcProcessor(IProcessor):
    """Procesa eventos realizando llamadas gRPC"""

    async def process(self, event: Event) -> Result[dict, ErrorType]:
        # Config: 5 intentos max, retry rápido (400ms)
        # Más rápido que HTTP por protocolo binario

        # Error classification por gRPC status codes
        # - NOT_FOUND, INVALID_ARGUMENT → PERMANENT
        # - UNAVAILABLE, DEADLINE_EXCEEDED → TRANSIENT
```

**Retry Timeline**: Más rápido que ApiCall (overhead reducido)

**Casos de uso**: Microservicios gRPC, llamadas internas de baja latencia

#### 3️⃣ LocalUseCaseProcessor (Local Methods)

```python
class LocalUseCaseProcessor(IProcessor):
    """Procesa eventos ejecutando UseCases locales"""

    async def process(self, event: Event) -> Result[dict, ErrorType]:
        # Config: 3 intentos max (menos que HTTP)
        # Retry más rápido: sin red overhead

        # Error classification local
        # - ValueError, TypeError → PERMANENT (bugs)
        # - Database timeouts → TRANSIENT
```

**Retry Timeline**: Fastest (sin red latency)

**Casos de uso**: Procesamiento interno, transformación de datos, validaciones complejas

#### 4️⃣ NoOpProcessor (Fallback)

```python
class NoOpProcessor(IProcessor):
    """Procesador por defecto para eventos no registrados"""

    async def process(self, event: Event) -> Result[dict, ErrorType]:
        # Retorna PERMANENT error inmediatamente
        # No hay reintentos
        # Marca el evento como FAILED
```

**Casos de uso**: Fallback seguro para eventos con tipo desconocido

### Error Classification Strategy

```python
# PERMANENT → FAILED (no reintentos)
PERMANENT_ERRORS = {
    4xx HTTP status codes,
    ValueError (business logic errors),
    gRPC NOT_FOUND,
    gRPC INVALID_ARGUMENT,
    Processor not found → NoOpProcessor
}

# TRANSIENT → TEMPORAL_ERROR (reintentos)
TRANSIENT_ERRORS = {
    5xx HTTP status codes,
    Connection timeouts,
    gRPC UNAVAILABLE,
    Database deadlocks
}
```

**Ejemplo práctico**:

```python
# ❌ Esta llamada siempre falla (4xx)
result = await http.get("https://api.example.com/user/invalid-id")
# Status 400: Bad Request → PERMANENT → FAILED

# ✅ Esta llamada puede reintentarse (5xx)
result = await http.get("https://api.example.com/user/123")
# Status 503: Service Unavailable → TRANSIENT → TEMPORAL_ERROR + retry
```

### Processor Registry

**Ubicación**: [app/infrastructure/processors/**init**.py](app/infrastructure/processors/__init__.py)

```python
processor_registry: dict[str, IProcessor] = {
    "api_call": ApiCallProcessor(http_client),
    "grpc": GrpcProcessor(),
    "local_usecase": LocalUseCaseProcessor(usecase_container),
    # Agregar más procesadores según necesidad
}

# Usar en evento:
event.processor_type = "api_call"  # Usa ApiCallProcessor
event.processor_type = "unknown"   # Usa NoOpProcessor (fallback)
```

### Integration in Event Handler

**Ubicación**: [app/infrastructure/redis/main.py](app/infrastructure/redis/main.py#L224-L310)

```python
async def handle_processing_event_queue(event_body, msg):
    # 1. Obtener procesador
    processor = processor_registry.get(
        event.processor_type,
        NoOpProcessor()  # Fallback si no existe
    )

    # 2. Ejecutar con reintentos
    result = await AsyncRetrying(
        stop=stop_after_attempt(processor.max_attempts),
        retry=retry_if_exception(classify_error),
        wait=wait_exponential(multiplier=0.1)
    ).wraps(processor.process)(event)

    # 3. Clasificar error
    if result.is_err():
        error_type = classify_error(result.unwrap_err())
        # PERMANENT → FAILED
        # TRANSIENT → TEMPORAL_ERROR

    # 4. Transicionar estado
    await use_case.execute(
        event,
        result_data=result.unwrap() if result.is_ok() else None,
        error=result.unwrap_err() if result.is_err() else None,
        is_failed=error_type == ErrorType.PERMANENT,
        is_temporal_error=error_type == ErrorType.TRANSIENT
    )

    # 5. Publicar a DLQ si FAILED/EXHAUSTED
    if event.state in [EventState.FAILED, EventState.EXHAUSTED]:
        await message_publisher.publish_failed_event(event, error)
```

---

## 🔄 Async Processor Pattern (Long-Running Tasks)

Para tareas de larga duración (ej: reportes, análisis), se usa **callback pattern**:

```
┌──────────────────────────────────┐
│  1. Event: PENDING               │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│  2. Handler: Get AsyncProcessor  │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│  3. Start background task        │
│     (asyncio.create_task)        │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│  4. Event: PROCESSING (callback) │
│     Topic: "event-result-{id}"   │
└──────────────────────────────────┘
                ↓
        (3+ horas de trabajo)
                ↓
┌──────────────────────────────────┐
│  5. Task completa, publica       │
│     resultado al topic callback  │
└──────────────────────────────────┘
                ↓
┌──────────────────────────────────┐
│  6. Event: COMPLETED             │
└──────────────────────────────────┘
```

**Implementación**:

```python
class AsyncLongRunningProcessor(IProcessor):
    async def process(self, event: Event) -> Result[dict, ErrorType]:
        # 1. Crear task en background
        task = asyncio.create_task(self._long_running_work())

        # 2. Registrar callback topic
        callback_topic = f"event-result-{event.id}"

        # 3. Retornar pendiente
        return Ok({"callback_topic": callback_topic, "task_id": task.id})

    async def _long_running_work(self):
        # Trabajo que toma minutos/horas
        result = await expensive_computation()

        # Publicar resultado al callback topic
        await broker.publish(result, stream=callback_topic)

        # Handler externo recibe y completa el evento
```

---

## 📤 Message Publisher & DLQ Routing

### IMessagePublisher Interface

**Ubicación**: [app/core/message_publisher.py](app/core/message_publisher.py)

```python
class IMessagePublisher(ABC):
    """Abstracción para publicar eventos a broker"""

    @abstractmethod
    async def publish_failed_event(
        self, event: Event, error: str
    ) -> Result[None, ErrorDetail]:
        """Publica evento FAILED a DLQ"""
        pass

    @abstractmethod
    async def publish_exhausted_event(
        self, event: Event, error: str
    ) -> Result[None, ErrorDetail]:
        """Publica evento EXHAUSTED (reintentos agotados) a DLQ"""
        pass

    @abstractmethod
    async def publish_success_event(
        self, event: Event, result: dict
    ) -> Result[None, ErrorDetail]:
        """Publica evento COMPLETED a stream de éxito (opcional)"""
        pass
```

### RedisMessagePublisher Implementation

**Ubicación**: [app/infrastructure/publishers/redis_message_publisher.py](app/infrastructure/publishers/redis_message_publisher.py)

```python
class RedisMessagePublisher(IMessagePublisher):
    """Publica eventos a Redis Streams"""

    async def publish_failed_event(self, event: Event, error: str):
        # Estructura del mensaje
        message = {
            "event_id": str(event.id),
            "event_name": event.name,
            "external_uuid": event.external_uuid,
            "state": event.state,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
            "type": "FAILED",
            "payload": event.payload,
            "context": {
                "processor_type": event.processor_type,
                "attempt": event.attempt_count,
                "last_error": event.last_error,
            }
        }

        # Publicar a stream "dlq-subject"
        await broker.publish(message, stream="dlq-subject")
```

**Mensaje Published**:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_name": "user.created",
  "external_uuid": "ext-uuid-12345",
  "state": "FAILED",
  "error": "HTTP 400: Invalid email format",
  "timestamp": "2025-12-28T15:30:45.123456",
  "type": "FAILED",
  "payload": { "email": "invalid-email" },
  "context": {
    "processor_type": "api_call",
    "attempt": 5,
    "last_error": "ValidationError"
  }
}
```

---

## 🔍 DLQ Handler & Monitoring

### DLQ Handler Implementation

**Ubicación**: [app/infrastructure/redis/dlq_handler.py](app/infrastructure/redis/dlq_handler.py)

```python
async def handle_dlq_message(body: dict, msg: RawMessage) -> None:
    """Consume eventos FAILED/EXHAUSTED desde DLQ"""

    try:
        # Structured logging con contexto completo
        logger.info(
            "DLQ Event Received",
            extra={
                "event_id": body.get("event_id", "unknown"),
                "event_name": body.get("event_name", "unknown"),
                "external_uuid": body.get("external_uuid", "unknown"),
                "state": body.get("state", "unknown"),
                "type": body.get("type", "unknown"),
                "error": body.get("error", "unknown"),
            }
        )

        # Manejo diferenciado por tipo
        if body.get("type") == "FAILED":
            # Error permanente - investigar
            logger.error("Permanent failure - investigate", extra=body)
        elif body.get("type") == "EXHAUSTED":
            # Reintentos agotados - escalar
            logger.warning("Retries exhausted - escalate", extra=body)

        # Ack: mensaje procesado
        await msg.ack()

    except Exception as e:
        # Nack: error al procesar, reintentar después
        logger.exception("DLQ handler failed", extra={"error": str(e)})
        await msg.nack()
```

### Logging Output

```json
{
  "message": "DLQ Event Received",
  "timestamp": "2025-12-28T15:30:45.123456",
  "level": "ERROR",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_name": "user.created",
  "external_uuid": "ext-uuid-12345",
  "state": "FAILED",
  "type": "FAILED",
  "error": "HTTP 400: Invalid email format"
}
```

---

## 🧪 Testing the Processor Pattern

### Unit Testing Processors

**Ubicación**: [tests/unit/test_sync_processors_unit.py](tests/unit/test_sync_processors_unit.py)

```python
@pytest.mark.asyncio
async def test_api_processor_success(processor):
    """Procesador HTTP exitoso"""
    result = await processor.process(event)
    assert result.is_ok()
    assert result.unwrap()["status"] == 200

@pytest.mark.asyncio
async def test_api_processor_permanent_error(processor):
    """Error permanente (4xx) → FAILED, sin reintentos"""
    result = await processor.process(event_400)
    assert result.is_err()
    error = result.unwrap_err()
    assert error.classification == ErrorType.PERMANENT

@pytest.mark.asyncio
async def test_api_processor_transient_error(processor):
    """Error transitorio (5xx) → TEMPORAL_ERROR, reintentos"""
    result = await processor.process(event_503)
    assert result.is_err()
    error = result.unwrap_err()
    assert error.classification == ErrorType.TRANSIENT
```

### Functional Testing End-to-End

**Ubicación**: [tests/functional/test_event_processing_complete_flow.py](tests/functional/test_event_processing_complete_flow.py)

```python
@pytest.mark.asyncio
async def test_happy_path_pending_to_completed():
    """Flow: PENDING → PROCESSING → COMPLETED"""
    event = create_event(processor_type="api_call", ...)

    # 1. Enqueue
    await enqueue_use_case.execute(...)

    # 2. Publicar a cola
    await broker.publish(event, stream="processing-event-subject")

    # 3. Handler procesa
    await handle_processing_event_queue(event, msg)

    # 4. Verificar estado final
    event_result = await repo.getOne(event.id)
    assert event_result.is_ok()
    db_event = event_result.unwrap()
    assert db_event.state == EventState.COMPLETED
    assert db_event.result_data == {"status": 200}

@pytest.mark.asyncio
async def test_transient_error_with_retry():
    """Flow: PENDING → TEMPORAL_ERROR → RETRYING"""
    event = create_event(processor_type="api_call", ...)

    # Mock: primeros 2 intentos fallan (503), tercero éxito
    processor_mock.process = AsyncMock(
        side_effect=[
            Err(ErrorType.TRANSIENT),
            Err(ErrorType.TRANSIENT),
            Ok({"status": 200})
        ]
    )

    await handle_processing_event_queue(event, msg)

    # Debe reintentarse
    assert processor_mock.process.call_count >= 2

@pytest.mark.asyncio
async def test_permanent_error_no_retry():
    """Flow: PENDING → FAILED (sin reintentos)"""
    event = create_event(processor_type="api_call", ...)

    # Mock: error 400
    processor_mock.process = AsyncMock(
        return_value=Err(ErrorType.PERMANENT)
    )

    await handle_processing_event_queue(event, msg)

    # Sin reintentos - intenta una sola vez
    assert processor_mock.process.call_count == 1

    # Publicado a DLQ
    published_messages = await dlq_handler.get_published()
    assert len(published_messages) == 1
    assert published_messages[0]["type"] == "FAILED"
```

---

## 🚀 Usage Examples

### Registrar nuevo Procesador

```python
# 1. Crear clase
class CustomProcessor(IProcessor):
    async def process(self, event: Event) -> Result[dict, ErrorType]:
        # Tu implementación
        pass

# 2. Registrar
processor_registry["custom"] = CustomProcessor()

# 3. Usar en evento
event.processor_type = "custom"
```

### Clasificar Errores Personalizados

```python
def classify_error(event: Event, error: Exception) -> ErrorType:
    # Lógica personalizada
    if isinstance(error, ValueError):
        return ErrorType.PERMANENT  # Bug en validación
    elif isinstance(error, TimeoutError):
        return ErrorType.TRANSIENT  # Reintentable
    else:
        return ErrorType.PERMANENT  # Por defecto, no reintentes
```

### Consumir Eventos de DLQ

```python
@app.event("dlq-subject")
async def handle_dlq(event: dict) -> None:
    logger.error(f"Event {event['event_id']} failed: {event['error']}")

    # Alertar a equipo
    await send_slack_notification(event)

    # O guardar en analytics BD
    await analytics_db.save_failure(event)
```

---

## ❓ Troubleshooting

### Evento stuck en TEMPORAL_ERROR

**Síntoma**: Evento permanece en TEMPORAL_ERROR por horas

**Causas**:

- Servicio externo inestable (retornando 503)
- Timeout de red recurrente
- Límite de reintentos no alcanzado

**Solución**:

1. Verificar logs de DLQ
2. Monitorear servicio externo
3. Aumentar max_attempts si es necesario

### Evento marcado como FAILED incorrectamente

**Síntoma**: Error que debería reintentarse marca como FAILED

**Causas**:

- Clasificación de error incorrecta
- Error no mapeado a TRANSIENT

**Solución**:

1. Revisar error classification logic
2. Agregar nuevo error a TRANSIENT_ERRORS
3. Reprocessar manualmente

### DLQ eventos acumulando

**Síntoma**: Muchos eventos en DLQ, poco movimiento

**Causas**:

- Handler dlq_handler caído
- Topic "dlq-subject" no subscrito
- Lógica de handler crasheando

**Solución**:

1. Verificar logs de handler
2. Revisar subscripción al topic
3. Hacer debug del handler code

### Processor no siendo ejecutado

**Síntoma**: Evento no procesado, evento sigue en PROCESSING

**Causas**:

- Procesador no registrado
- Nombre de tipo incorrecto

**Solución**:

1. Verificar processor_registry
2. Validar event.processor_type
3. Agregar logging antes de get()

---

## 📊 Current Status

### Tests Coverage

- ✅ **203 tests passing** (98.9% success rate)
- ✅ **86.92% coverage** (gate mínimo: ≥85%, exceeded by 1.92%)
- ✅ Processor tests: 26 unit tests (sync processors)
- ✅ Integration tests: 5 end-to-end flows
- ✅ Message Publisher tests: 14 unit tests
- ✅ DLQ Handler tests: 16 unit tests
- ✅ Redis handler tests: 142 tests (including 2 updated for processor pattern)

### Code Quality

- ✅ **Ruff**: ALL PASSED (linting & formatting)
- ✅ **mypy**: strict mode (type-safe)
- ✅ **Coverage Gate**: 86.92% (exceeds 85% requirement)
- ✅ **Pre-commit hooks**: Ready for integration

### Architecture

- ✅ Clean Architecture (3 capas)
- ✅ Dependency Injection (todos los componentes)
- ✅ Repository Pattern
- ✅ Unit of Work Pattern
- ✅ **Processor Pattern** (✨ NEW - Phases 5-6)
  - 4+ processor types (ApiCall, Grpc, LocalUseCase, NoOp)
  - Error classification (PERMANENT, TRANSIENT)
  - UX-optimized retry strategy (p95 1700ms)
  - Message publisher abstraction + Redis implementation
  - DLQ routing with structured logging
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

## Getting Help

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

| Versión | Fecha      | Cambios                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v3.1    | 2025-12-28 | **PROCESSEVENIDEALUSECASE COMPLETE (Phases 1-4)**: Refactorized Development Workflow section with comprehensive 4-stage pipeline (fetch→validate_and_lock→process_with_retries→persist_outcome→execute). Added detailed implementation guides for each stage, pattern matching async orchestration (no and_then), 34 unit tests (89% coverage on neo_event_usecase.py), comprehensive test strategy breakdown (validate_lock, process_with_retries, persist_outcome, coverage_gaps, execute_orchestration), quality gates validation (Ruff PASS, mypy PASS strict mode), and troubleshooting guide. |
| v3.0    | 2025-12-28 | **PROCESSOR PATTERN COMPLETE (Phases 5-6)**: Added comprehensive Processor Pattern documentation covering 4+ processor types (ApiCall, Grpc, LocalUseCase, NoOp), error classification strategy, async/callback pattern, Message Publisher, DLQ routing, comprehensive testing strategy, and troubleshooting guide. 203 tests, 86.92% coverage.                                                                                                                                                                                                                                                     |
| v2.1    | 2025-12-28 | **Added "Lo que no está, no falla" principle**: Agregado como principio core con sección dedicada, ejemplos prácticos, red flags y métricas de éxito. Incluido en Common Pitfalls y Key Takeaways.                                                                                                                                                                                                                                                                                                                                                                                                  |
| v2.0    | 2025-12-27 | **Complete rewrite**: Reorganizado para ser más práctico y repetible. Added concurrency patterns, simplified commands, added typical workflow example. Agregados principios SOLID explícitamente.                                                                                                                                                                                                                                                                                                                                                                                                   |
| v1.0    | 2024-12-10 | Versión inicial                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

---

**Última actualización**: 2025-12-28
**Status**: ✅ PHASE 4 COMPLETE - ProcessEventIdealUseCase fully implemented and tested (89% coverage, Ruff + mypy clean)
**Next Steps**: Functional testing e2e with real DB, Agents.md integration guide, full suite coverage gate
