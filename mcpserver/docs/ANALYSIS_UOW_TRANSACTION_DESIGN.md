# Análisis: Diseño de UnitOfWork y Transacciones en UseCases

## 🎯 Problema Identificado

### Patrón Actual (Problemático)

```python
# En app/core/usecases/event_usecases.py:138
class EnqueueEventUseCase:
    async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
        async with self.uow:  # ← UseCase ABRE contexto
            # Lógica
            evt = Event(...)
            return await self.uow.events.save_or_resolve_one(evt)
        # ← UseCase CIERRA contexto
```

### Limitaciones

1. **No composable**: Si queremos coordinar 2+ use cases en 1 transacción, cada uno crea la suya
2. **Rigidez**: No podemos orquestar enqueue + publish en una sola transacción atómica
3. **No testeable en composición**: Tests de un use case no pueden compartir transacción con otro
4. **Duplicado**: Handler + UseCase abriendo contextos independientes

### Flujo Actual (enqueue-event)

```
Handler (redis/main.py)
├─ crea UoW pero NO context manager
├─ llama UseCase.execute()
│  └─ UseCase ABRE su propio context (async with self.uow)
│     ├─ Guarda evento en BD
│     ├─ COMMIT automático en __aexit__
│     └─ CIERRA sesión
├─ (sesión ya cerrada)
├─ Podría publicar a processing-subject AQUÍ
│  └─ ❌ Pero si publish falla, evento ya fue commiteado
│  └─ ❌ No hay transacción atómica
└─ ack/nack
```

---

## 🔄 Alternativas de Diseño

### **ALTERNATIVA A: UseCase SIN Context Manager** (Recommended)

#### Patrón

```python
# Core layer
class EnqueueEventUseCase(AsyncUseCase[...]):
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
        # ❌ NO: async with self.uow
        # ✅ SÍ: Solo usa repositorios, delegando transacción al caller

        # Normalizar datos
        normalized_payload = self._normalize_json(input.payload)

        # Crear entidad
        evt = Event(
            id=input.id if input.id is not None else uuid4(),
            name=input.name,
            payload=normalized_payload or {},
            context=input.context or {},
            state=input.state or EventState.CREATED,
        )

        # ✅ Guardar sin abrir transacción (la abre el caller)
        op_result = await self.uow.events.save_or_resolve_one(evt)
        return op_result.and_then(lambda saved_event: Ok(self.as_output(saved_event)))
```

#### En Handler

```python
# Infrastructure layer (redis/main.py)
@EnqueueEventSubscriber
async def handle_enqueue_event(
    event: EnqueuedEventUseCaseInput,
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        # ✅ Handler ABRE transacción
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            usecase = EnqueueEventUseCase(uow)

            # 1. Enqueue en BD
            result_enqueue = await usecase.execute(event)

            if result_enqueue.is_ok():
                event_saved = result_enqueue.unwrap()

                # 2. Publicar a processing DENTRO MISMA TRANSACCIÓN
                await broker.publish(
                    {
                        "event_id": str(event_saved.id),
                        "name": event_saved.name,
                        "state": event_saved.state.value,
                    },
                    stream="processing-event-subject"
                )
                # ✅ AQUÍ se hace commit automático (__aexit__)
                await msg.ack()
            else:
                await msg.nack()
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.nack()
```

#### Ventajas ✅

- 🎯 **Composable**: Múltiples use cases en 1 transacción
- 🎯 **Clarito**: Handler orquesta transacción, UseCase es puro
- 🎯 **Testeable**: Compose use cases en tests sin conflicto de contextos
- 🎯 **Atómico**: enqueue + publish en 1 transacción
- 🎯 **Flexible**: Handler decide dónde abrir/cerrar

#### Desventajas ❌

- ⚠️ UseCase asume transacción ya abierta (requiere documentación clara)
- ⚠️ Si handler olvida abrir transacción → error en runtime

#### Diagrama

```
Handler
└─ async with UoW:
   ├─ UseCase1.execute()  ← usa UoW, no abre
   ├─ Action(publish)     ← dentro misma transacción
   └─ commit en __aexit__  ← ATÓMICO

Test
└─ async with UoW:
   ├─ UseCase1.execute()
   ├─ UseCase2.execute()
   └─ assert estado combinado
```

---

### **ALTERNATIVA B: UseCase Recibe Explícitamente si Maneja Transacción**

#### Patrón

```python
class EnqueueEventUseCase(AsyncUseCase[...]):
    def __init__(self, uow: UnitOfWork, manage_transaction: bool = False):
        self.uow = uow
        self.manage_transaction = manage_transaction

    async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
        # Abre transacción SOLO si manage_transaction=True
        if self.manage_transaction:
            async with self.uow:
                return await self._do_execute(input)
        else:
            # Asume transacción ya abierta
            return await self._do_execute(input)

    async def _do_execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
        # Lógica
        evt = Event(...)
        return await self.uow.events.save_or_resolve_one(evt)
```

#### Uso

```python
# Caso 1: UseCase abre su transacción (legacy, simple)
usecase = EnqueueEventUseCase(uow, manage_transaction=True)
result = await usecase.execute(input)

# Caso 2: Handler orquesta transacción
async with AsyncSQLAlchemyUnitOfWork(session) as uow:
    usecase = EnqueueEventUseCase(uow, manage_transaction=False)
    result1 = await usecase.execute(input1)
    result2 = await other_usecase.execute(input2)
    # Ambos en misma transacción
```

#### Ventajas ✅

- ✅ Backward compatible (manage_transaction=True por defecto)
- ✅ Permite ambos patrones gradualmente

#### Desventajas ❌

- ⚠️ Más complejidad en UseCase
- ⚠️ Flag booleano no es muy explícito semánticamente

---

### **ALTERNATIVA C: Transactional Decorator Pattern**

#### Patrón

```python
from functools import wraps

def transactional(manage_transaction: bool = False):
    """Decorator que maneja transacción del UoW"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, input, *args, **kwargs):
            if manage_transaction:
                async with self.uow:
                    return await func(self, input, *args, **kwargs)
            else:
                return await func(self, input, *args, **kwargs)
        return wrapper
    return decorator

class EnqueueEventUseCase(AsyncUseCase[...]):
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    @transactional(manage_transaction=False)  # Configurar por use case
    async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
        evt = Event(...)
        return await self.uow.events.save_or_resolve_one(evt)
```

#### Ventajas ✅

- ✅ Semánticamente explícito
- ✅ Reutilizable en múltiples use cases

#### Desventajas ❌

- ⚠️ Más "magia" con decoradores
- ⚠️ Complica el flow de código

---

### **ALTERNATIVA D: UnitOfWork Context Manager Tracking**

#### Patrón

```python
class AsyncSQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession, owns_session: bool = False):
        self._session = session
        self._owns_session = owns_session
        self._context_depth = 0  # ← NUEVA: Track nesting
        self._courses: CourseRepository | None = None
        self._events: EventRepository | None = None

    async def __aenter__(self) -> "AsyncSQLAlchemyUnitOfWork":
        self._context_depth += 1
        if self._context_depth == 1:  # Primer entrada
            self._courses = AsyncSQLAlchemyCourseRepository(self._session)
            self._events = AsyncSQLAlchemyEventRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._context_depth -= 1
        if self._context_depth == 0:  # Última salida
            if exc_type is not None:
                await self.rollback()
            else:
                await self.commit()
            # close session...
```

Así permite:

```python
async with uow:  # depth=1
    await usecase1.execute(input)  # usa uow sin context

    async with uow:  # depth=2 (noop, reutiliza)
        await usecase2.execute(input)
    # depth vuelve a 1

    await broker.publish(...)
# depth=0, commit aquí
```

#### Ventajas ✅

- ✅ Permite nesting de context managers
- ✅ Transparente para use cases

#### Desventajas ❌

- ⚠️ Complejidad en UoW (tracking depth)
- ⚠️ Semántica confusa (¿qué hace nested context?)
- ⚠️ Riesgo de rollback parcial

---

## 🏆 Recomendación: ALTERNATIVA A

### Por Qué

1. **Claridad**: UseCase es función pura (no maneja contexto transaccional)
2. **Composabilidad**: Handler orquesta múltiples use cases en 1 transacción
3. **Testabilidad**: Tests pueden compo usar cases sin conflictos
4. **SOLID SRP**: Cada componente tiene responsabilidad clara
   - UseCase: Lógica de negocio
   - Handler: Orquestación y transacción
   - UoW: Ciclo de vida de sesión

### Implementación Propuesta

#### Paso 1: Cambiar EnqueueEventUseCase

```python
# ANTES
async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
    async with self.uow:  # ❌ UseCase abre
        evt = Event(...)
        return await self.uow.events.save_or_resolve_one(evt)

# DESPUÉS
async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
    # ✅ UseCase NO abre contexto, asume ya abierto
    evt = Event(...)
    return await self.uow.events.save_or_resolve_one(evt)
```

#### Paso 2: Handler Orquesta Transacción

```python
@EnqueueEventSubscriber
async def handle_enqueue_event(
    event: EnqueuedEventUseCaseInput,
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        # ✅ Handler abre transacción
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            usecase = EnqueueEventUseCase(uow)

            # Enqueue
            result = await usecase.execute(event)

            if result.is_ok():
                value = result.unwrap()

                # Publish (dentro misma transacción)
                await broker.publish(
                    {"event_id": str(value.id), "name": value.name},
                    stream="processing-event-subject"
                )
                # Commit en __aexit__
                await msg.ack()
            else:
                await msg.nack()
    except Exception as e:
        await msg.nack()
```

#### Paso 3: Tests Componen Use Cases

```python
async def test_enqueue_and_process_together(uow_factory):
    """Test: 2 use cases en 1 transacción"""
    async with uow_factory() as uow:
        enqueue_uc = EnqueueEventUseCase(uow)
        process_uc = ProcessEventUseCase(uow)

        # Ambos usan MISMO UoW (misma transacción)
        result1 = await enqueue_uc.execute(input1)
        assert result1.is_ok()

        result2 = await process_uc.execute(input2)
        assert result2.is_ok()

        # Ambos committed juntos en __aexit__
```

---

## 📋 Checklist de Cambios

### Archivos a Modificar

```
app/
├── core/usecases/
│   └── event_usecases.py           (MODIFY: remove async with self.uow)
│       ├─ EnqueueEventUseCase
│       ├─ ProcessEventUseCase
│       └─ (otros use cases sin context manager)
│
└── infrastructure/
    └── redis/
        └── main.py                 (MODIFY: add async with uow)
            ├─ handle_enqueue_event
            ├─ handle_processing_event_queue
            └─ (agregar orchestration)

tests/
├── unit/
│   └── test_enqueue_event_usecase_unit.py  (MODIFY: tests no esperan context manager)
│
└── functional/
    ├── test_enqueue_event_usecase_functional.py (MODIFY: handler maneja contexto)
    └── test_redis_enqueue_handler.py (NEW: test composición)
```

### Test Changes

**Antes**: Tests esperaban context manager en UseCase

```python
async def test_use_case(uow_mock):
    use_case = EnqueueEventUseCase(uow_mock)
    result = await use_case.execute(input)  # ✅ Funciona sin context
```

**Después**: Mismo test, pero UseCase asume contexto ya abierto

```python
async def test_use_case(uow_factory):
    async with uow_factory() as uow:  # ← Handler abre
        use_case = EnqueueEventUseCase(uow)
        result = await use_case.execute(input)  # ✅ Funciona dentro contexto
        assert result.is_ok()
```

---

## 🎯 Pros & Contras Resumidos

| Alternativa         | Composable | Testeable | Claridad | Complejidad |
| ------------------- | ---------- | --------- | -------- | ----------- |
| **A (Recommended)** | ⭐⭐⭐     | ⭐⭐⭐    | ⭐⭐⭐   | ⭐          |
| B (Flag)            | ⭐⭐       | ⭐⭐      | ⭐⭐     | ⭐⭐        |
| C (Decorator)       | ⭐⭐       | ⭐⭐      | ⭐⭐     | ⭐⭐⭐      |
| D (Depth tracking)  | ⭐⭐⭐     | ⭐        | ⭐       | ⭐⭐⭐⭐    |

---

## 📝 Próximos Pasos

1. **Validar alternativa A** con Peer Review
2. **Refactorizar** `EnqueueEventUseCase` (remove context manager)
3. **Actualizar** `handle_enqueue_event` (add context manager)
4. **Refactorizar** tests de acuerdo al nuevo patrón
5. **Implementar Mejora #2** (publish to processing) ya con patrón correcto
6. **Extender a otros use cases** (ProcessEventUseCase, etc)

---

## 🔗 Referencias

- [Agents.md - Development Workflow](../Agents.md)
- [IMPROVEMENTS_ROADMAP.md](IMPROVEMENTS_ROADMAP.md)
- [IMPROVEMENTS_SESSION_OWNERSHIP.md](IMPROVEMENTS_SESSION_OWNERSHIP.md)
