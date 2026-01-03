# 📊 ROADMAP: Plan de Implementación 2026

**Status**: ✅ Arquitectura aprobada - Iniciando Fases

---

## 📅 Timeline de Implementación

```
SEMANA 1: Refactorización (5 días)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DÍA 1 (HOY): FASE 1 - Refactor UseCase
├─ Remove async with from EnqueueEventUseCase
├─ Keep business logic
├─ Update docstrings
├─ Test: All passing
└─ Files: app/core/usecases/event_usecases.py

DÍA 2: FASE 2 - Update Handlers
├─ Add async with AsyncSQLAlchemyUnitOfWork
├─ Wrap handler logic
├─ Keep error handling
├─ Test: All passing
└─ Files: app/infrastructure/redis/main.py

DÍA 3: FASE 3 - Migrate Tests
├─ Update unit tests (remove context)
├─ Update functional tests (add context)
├─ Add atomicity validation
├─ Validate: 100+ tests, coverage ≥85%
└─ Files: tests/unit/*, tests/functional/*

DÍA 4: FASE 4 - Documentation
├─ Update Agents.md
├─ Create TRANSACTION_PATTERN.md
├─ Add use case examples
└─ Files: docs/

DÍA 5: MEJORA #2 - Publish to Processing
├─ Add broker.publish() in handlers
├─ Guarantee atomicity
├─ Test end-to-end
└─ Unblock event processing pipeline

SEMANA 2: Features Adicionales (5 días)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DÍA 6-7: MEJORA #3 - MessagePublisher Gateway
├─ Create abstraction for publish
├─ Decouple from RedisBroker
├─ Add tests
└─ Enable different publishers

DÍA 8-9: MEJORA #5 - Retry + DLQ
├─ Add retry policy
├─ Implement DLQ
├─ Handle poison pills
└─ Production resilience

DÍA 10: MEJORA #4 - Structured Logging
├─ JSON logging
├─ Context tracking
├─ Performance metrics
└─ Observability boost
```

---

## 🎯 Métricas de Éxito

### Por Fase

| Fase  | Métrica        | Target    | Status              |
| ----- | -------------- | --------- | ------------------- |
| **1** | Tests passing  | 99+       | 🔴 Pending          |
| **1** | mypy strict    | 0 errors  | 🟢 Current          |
| **1** | ruff check     | 0 issues  | 🟢 Current          |
| **2** | Handler wraps  | 100%      | 🔴 Pending          |
| **2** | Error handling | Complete  | 🔴 Pending          |
| **3** | Test coverage  | ≥85%      | 🟢 Current (92.17%) |
| **4** | Documentation  | Complete  | 🔴 Pending          |
| **5** | E2E atomicity  | Validated | 🔴 Pending          |

### Globales

- ✅ Coverage: 92.17% → Mantener ≥85%
- ✅ Tests: 99 passing → Mantener 100+
- ✅ Type safety: mypy strict → Mantener 0 errors
- ✅ Code quality: ruff → Mantener 0 issues

---

## 🔧 Cambios Específicos por Archivo

### app/core/usecases/event_usecases.py

**FASE 1 - Remove async with**

```python
# LÍNEA 138-145 (ANTES)
async def execute(
    self, input: EnqueuedEventUseCaseInput
) -> Result[EnqueuedEventUseCaseOutput, ErrorDetail]:
    async with self.uow:  # ❌ REMOVE
        evt = Event(
            name=input.name,
            ...
        )
        return await self.uow.events.save_or_resolve_one(evt)

# LÍNEA 138-145 (DESPUÉS)
async def execute(
    self, input: EnqueuedEventUseCaseInput
) -> Result[EnqueuedEventUseCaseOutput, ErrorDetail]:
    # Assumes caller manages transaction context
    # See: docs/TRANSACTION_PATTERN.md
    evt = Event(
        name=input.name,
        ...
    )
    return await self.uow.events.save_or_resolve_one(evt)
```

**Archivos similares**:

- app/core/usecases/course_usecases.py (check if has async with)

---

### app/infrastructure/redis/main.py

**FASE 2 - Add handler context**

```python
# LÍNEA ~50-70 (ANTES)
@EnqueueEventSubscriber
async def handle_enqueue_event(
    msg: StreamMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    event = msg.data
    uow = AsyncSQLAlchemyUnitOfWork(session, owns_session=False)  # ❌ No context
    usecase = EnqueueEventUseCase(uow)
    result = await usecase.execute(event)

# LÍNEA ~50-70 (DESPUÉS)
@EnqueueEventSubscriber
async def handle_enqueue_event(
    msg: StreamMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    event = msg.data
    async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:  # ✅ Context
        usecase = EnqueueEventUseCase(uow)
        result = await usecase.execute(event)

        if result.is_ok():
            # MEJORA #2
            await broker.publish(
                {
                    "event_id": str(result.unwrap().id),
                    "state": "processing",
                },
                stream="processing-event-subject"
            )
            await msg.ack()
        else:
            await msg.nack()
```

**Handlers a actualizar**:

- handle_enqueue_event
- handle_processing_event_queue (future)

---

### tests/unit/test_enqueue_event_usecase_unit.py

**FASE 3 - Remove context expectations**

```python
# ANTES: Test esperaba context manager
def test_u1_valid_input_new_event(uow_mock):
    use_case = EnqueueEventUseCase(uow=uow_mock)
    # Mock: uow_mock.__aenter__ = AsyncMock(return_value=uow_mock)
    # Mock: uow_mock.__aexit__ = AsyncMock(return_value=None)

# DESPUÉS: Test simple sin context
@pytest.mark.asyncio
async def test_u1_valid_input_new_event(uow_mock):
    use_case = EnqueueEventUseCase(uow=uow_mock)
    result = await use_case.execute(valid_input)
    assert result.is_ok()
```

**Tests a actualizar**:

- test_enqueue_event_usecase_unit.py
- test_transition_event_unit.py
- Otros unit tests

---

### tests/functional/test_enqueue_event_usecase_functional.py

**FASE 3 - Add handler context**

```python
# ANTES: UseCase maneja contexto
async with uow_factory() as uow:
    use_case = EnqueueEventUseCase(uow)
    result = await use_case.execute(input)

# DESPUÉS: Handler-style context (como será en production)
async with uow_factory() as uow:
    use_case = EnqueueEventUseCase(uow)
    result = await use_case.execute(input)

    if result.is_ok():
        # Simular publish
        published = await broker.publish({...})
        assert published.is_ok()

    # COMMIT automático en __aexit__
```

---

## 📝 Checklist por Fase

### ✅ FASE 1: Refactor UseCase

```
☐ Remove async with from EnqueueEventUseCase.execute()
☐ Remove async with from ProcessEventUseCase.execute() (if exists)
☐ Update docstrings: "Caller manages transaction"
☐ Update type hints (if needed)
☐ Run: pytest tests/unit/ -v
  └─ Expected: All passing
☐ Run: mypy app
  └─ Expected: No issues
☐ Run: ruff check . && ruff format .
  └─ Expected: No issues
☐ Commit: refactor(usecases): remove context manager from use cases
```

### ✅ FASE 2: Update Handlers

```
☐ Add async with AsyncSQLAlchemyUnitOfWork(...) to handle_enqueue_event
☐ Verify session ownership: owns_session=False
☐ Update error handling: ack/nack correcto
☐ Add try/finally for exception safety
☐ Run: pytest tests/functional/test_redis_basics.py -v
  └─ Expected: All passing
☐ Run: pytest tests/unit/test_redis_handlers_unit.py -v
  └─ Expected: All passing
☐ Run: mypy + ruff
  └─ Expected: No issues
☐ Commit: refactor(redis): add transaction context to handlers
```

### ✅ FASE 3: Migrate Tests

```
☐ Update unit test mocks (remove context expectations)
☐ Update functional test fixtures (add context)
☐ Add atomicity validation tests
☐ Verify coverage: pytest --cov=app
  └─ Expected: ≥85%
☐ Run: pytest -v --tb=short
  └─ Expected: 100+ passing, 2 skipped
☐ Commit: test(migration): update tests for handler-managed transactions
```

### ✅ FASE 4: Documentation

```
☐ Create: docs/TRANSACTION_PATTERN.md
  ├─ Explain owner_session parameter
  ├─ Show handler example
  └─ Show use case example
☐ Update: docs/DEVELOPMENT.md
  ├─ Add transaction section
  ├─ Add new use case checklist
  └─ Add composition patterns
☐ Update: Agents.md
  ├─ Update workflow section
  ├─ Update testing patterns
  └─ Update examples
☐ Review: All docs spell-checked
☐ Commit: docs: add transaction pattern documentation
```

### ✅ FASE 5: Mejora #2

```
☐ Add broker.publish() in handle_enqueue_event
  ├─ Inside async with context
  ├─ Stream: "processing-event-subject"
  └─ Payload: event details
☐ Update test: validate atomicity
  ├─ If publish fails → rollback
  ├─ If handler crash → no duplication
  └─ Normal flow → atomic
☐ Verify: E2E redis flow
  ├─ enqueue-event-subject → handler
  ├─ handler → save + publish
  ├─ save → BD
  ├─ publish → processing-event-subject
  └─ All in 1 TX
☐ Commit: feat(redis): publish to processing-event-subject (atomic)
```

---

## 🚨 Riesgos & Mitigaciones

| Riesgo                  | Probabilidad | Impacto | Mitigación        |
| ----------------------- | ------------ | ------- | ----------------- |
| Tests fallan en Fase 1  | Media        | Alto    | Revert + análisis |
| Handler context difícil | Baja         | Medio   | Usar try/finally  |
| Coverage baja en Fase 3 | Baja         | Alto    | Agregar tests     |
| Documento inconsistente | Baja         | Bajo    | Peer review       |

---

## ✨ Beneficios Esperados

### Después de Fase 1-2

- ✅ Arquitectura limpia: Handler orquesta, UseCase ejecuta
- ✅ Composición: 2+ use cases en 1 TX
- ✅ Testing: Use cases más simples sin TX context

### Después de Fase 3

- ✅ Tests migrados: 100+ passing
- ✅ Coverage: Mantenido ≥85%
- ✅ Confianza: Patrón validado

### Después de Fase 4

- ✅ Documentación clara
- ✅ Onboarding mejorado
- ✅ Patrón replicable

### Después de Fase 5 (Mejora #2)

- ✅ Atomicidad garantizada: save + publish
- ✅ Event processing pipeline: 100% funcional
- ✅ Escalable: Listo para Mejora #3-5

---

## 🎯 Decisiones Pendientes

**¿Iniciar hoy Fase 1?**

- [ ] Sí, implementar todas las fases esta semana
- [ ] Sí, pero paso a paso día por día
- [ ] No, esperar siguiente semana

**¿Parar en Fase 5 o continuar?**

- [ ] Implementar también Mejora #3 (MessagePublisher)
- [ ] Dejar para siguiente semana

---

**Última actualización**: 3 de Enero de 2026  
**Próxima revisión**: Después de Fase 1 completada
