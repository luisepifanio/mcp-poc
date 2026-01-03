# 📋 Peer Review - Mejoras Pendientes

**Actualizado**: 3 de enero de 2026

---

## ✅ Completadas (Este Sprint)

### 1. Error Handling Improvements

- **Status**: ✅ COMPLETADA
- **Implementación**: Retry strategy con exponencial backoff using tenacity
- **Commit**: `2cc1ba3` - feat(redis): implement retry strategy with exponential backoff
- **Alcance**:
  - Enqueue: 3 intentos (1s, 2s, 4s backoff)
  - Publish: 5 intentos (0.5s, 1s, 2s, 4s, 8s backoff)
  - Atomicidad preservada: publish fail → rollback DB
  - Observabilidad: Logs estructurados por retry attempt
- **Documentación**: [RETRY_STRATEGY.md](docs/RETRY_STRATEGY.md), [RETRY_IMPLEMENTATION_SUMMARY.md](docs/RETRY_IMPLEMENTATION_SUMMARY.md)
- **Tests**: 102 passing, 91.39% coverage ✅

---

## ⏳ Backlog (Próximas Mejoras)

### 📌 Mejora #3: MessagePublisher Abstraction

**Descripción**: Desacoplar de RedisBroker específico

**Problema Actual**:

```python
# ❌ Fuerte acoplamiento a RedisBroker
async def handle_enqueue_event(..., broker: RedisBroker):
    await broker.publish({...})  # Depende de RedisBroker
```

**Solución Propuesta**:

```python
# ✅ Interfaz abstracta
class MessagePublisher(ABC):
    @abstractmethod
    async def publish(self, data: dict, stream: str) -> Result:
        pass

# ✅ Uso agnóstico de implementación
async def handle_enqueue_event(..., publisher: MessagePublisher):
    await publisher.publish({...})  # Puede ser Redis, RabbitMQ, etc.
```

**Beneficios**:

- 🔄 Diferentes backends (Redis, RabbitMQ, Kafka, etc.)
- 🧪 Testing más fácil (mock publisher)
- 🏗️ Clean Architecture: handler no conoce detalles
- 📈 Escalabilidad: cambiar backend sin cambiar lógica

**Estimado**: 2 días  
**Complejidad**: Media  
**Prioridad**: ALTA (enabler para otras mejoras)

---

### 📌 Mejora #4: Structured Logging

**Descripción**: Logging JSON estructurado con contexto

**Problema Actual**:

```python
# ❌ Logs de texto plano
logger.info(f"Event {event.id} enqueued")
logger.warning(f"Retry attempt {attempt_num}")
```

**Solución Propuesta**:

```python
# ✅ JSON estructurado para parsing/agregación
logger.info("event_enqueued", extra={
    "event_id": str(event.id),
    "event_name": event.name,
    "timestamp": datetime.utcnow().isoformat(),
    "duration_ms": elapsed_time,
})

logger.warning("retry_attempt", extra={
    "event_id": str(event.id),
    "attempt": attempt_num,
    "reason": str(error),
    "next_backoff_seconds": backoff_seconds,
})
```

**Beneficios**:

- 📊 Parsing automático en ELK Stack / Datadog
- 🔍 Búsquedas por field (e.g., `event_id`, `attempt`)
- 📈 Métricas: count by status, latency percentiles
- 🚨 Alertas: pattern matching automático

**Stack Propuesto**: python-json-logger  
**Estimado**: 1 día  
**Complejidad**: Baja  
**Prioridad**: MEDIA (observabilidad)

---

### 📌 Mejora #5: Retry + Dead Letter Queue (DLQ)

**Descripción**: Manejo avanzado de failures con DLQ

**Problema Actual**:

```
Event falla después de todos los retries
→ Message nack'd → Redis redelivery infinito
→ Posible infinite loop si siempre falla
```

**Solución Propuesta**:

```
Event falla N veces (N=max_retries)
→ Move to Dead Letter Queue
→ Background job procesa DLQ periódicamente
→ Manual review + requeue OR discard

Redis Topic (enqueue-event-subject)
    ↓
    Handler (3x enqueue, 5x publish retries)
    ↓ (si falla after all retries)
DLQ (redis-dlq)
    ↓
Background Job (cada hora)
    ├→ Check if recoverable (DB online, etc.)
    ├→ Si sí: Republish a topic principal
    └→ Si no: Log y mark as unrecoverable
```

**Beneficios**:

- 🛡️ Previene infinite loops
- 👀 Visibilidad de eventos fallidos (DLQ observable)
- 🔧 Manual recovery capability
- 📊 Metrics: DLQ size, requeue rate

**Estimado**: 2 días  
**Complejidad**: Media-Alta  
**Prioridad**: ALTA (production safety)

---

### 📌 Mejora #6: Background Event Reprocessing (NEW)

**Descripción**: Async task para recuperar eventos stuck (CREATED/PENDING)

**Problema Identificado** (por usuario):

```
Eventos pueden quedar atascados en CREATED/PENDING:
- App crashea durante procesamiento
- Sistema offline > umbral timeout
- Race conditions no capturadas
```

**Solución**:

```
APScheduler Job (cada 5 minutos)
    ↓
Find CREATED/PENDING eventos > 10min age
    ↓
For each: Republish a enqueue-event-subject
    ↓
Max 3 recovery attempts per event
    ↓
Si agota: Mark as unrecoverable, log event
```

**Estimado**: 3-5 días  
**Complejidad**: Media  
**Prioridad**: ALTA (resilience)  
**Documentación**: [BACKLOG_BACKGROUND_REPROCESSING.md](docs/BACKLOG_BACKGROUND_REPROCESSING.md)

---

## 🗂️ Stack por Mejora

| Mejora                          | Tecnologías                   | Archivos Clave                        |
| ------------------------------- | ----------------------------- | ------------------------------------- |
| **#3: MessagePublisher**        | ABC, Dependency Injection     | `app/core/publisher.py` (NEW)         |
| **#4: Structured Logging**      | python-json-logger, logconfig | `app/core/logconfig.py` (MODIFY)      |
| **#5: DLQ**                     | Redis Streams, APScheduler    | `app/infrastructure/dlq/` (NEW)       |
| **#6: Background Reprocessing** | APScheduler, SQLAlchemy       | `app/infrastructure/scheduler/` (NEW) |

---

## 📊 Esfuerzo Total

```
Mejora #3: MessagePublisher       2 días  ███████░░ 30%
Mejora #4: Structured Logging     1 día   ████░░░░░ 15%
Mejora #5: Retry + DLQ            2 días  ███████░░ 30%
Mejora #6: Background Reprocessing 3 días ██████░░░ 25%
───────────────────────────────────────────────────
Total:                            8 días  ██████████ 100%
```

**Timeline Estimado**: 2 semanas (con parallelization)

---

## 🎯 Opciones de Priorización

### Opción A: Full Sprint (8 días)

- ✅ Todas las mejoras implementadas
- ✅ Sistema "production-hardened"
- ❌ Más tiempo de desarrollo
- **Recomendado si**: Deadline de producción próximo

### Opción B: MVP (4-5 días)

- Mejora #3 (MessagePublisher) - Habilitador arquitectónico
- Mejora #5 (DLQ) - Production safety
- ❌ Sin observabilidad avanzada
- **Recomendado si**: Iteración rápida importante

### Opción C: Observabilidad First (3-4 días)

- Mejora #4 (Structured Logging) - Debugging
- Mejora #6 (Background Reprocessing) - Resilience
- ❌ Sin abstracción de publisher
- **Recomendado si**: Production issues son priority

---

## 🔗 Dependencias entre Mejoras

```
Mejora #3 (MessagePublisher)
├─ Independiente
└─ Enabler para: #4, #5 (decoupling)

Mejora #4 (Structured Logging)
├─ Depende de: Nada
└─ Beneficia: #5, #6 (better debugging)

Mejora #5 (Retry + DLQ)
├─ Depende de: #3 (opcional pero recomendado)
└─ Enabler para: #6 (recovery from DLQ)

Mejora #6 (Background Reprocessing)
├─ Depende de: #5 (DLQ infrastructure)
└─ Independiente: Pero se integra bien con #4 (logging)
```

**Orden Recomendado**: #3 → #5 → #6 → #4

---

## 📋 Checklist para Siguiente Sprint

### Pre-Sprint Planning

- [ ] Revisar y aprobar diseño de Mejora #3 (MessagePublisher)
- [ ] Validar stack de logging (python-json-logger vs alternatives)
- [ ] Confirmar DLQ strategy con equipo DevOps
- [ ] Estimar con precision de 2x en timing

### Durante Implementation

- [ ] Mantener 85%+ coverage gate
- [ ] Actualizar Agents.md con nuevos patterns
- [ ] Documentación en paralelo (no al final)
- [ ] Tests: unit + functional + integration

### Antes de Deploy

- [ ] Peer review cross-team
- [ ] Load testing para retry strategy
- [ ] Monitoring dashboard creado
- [ ] Runbook para operaciones

---

## 💡 Quick Wins (Sin estimado)

Si quieres avances rápidos mientras planeas sprint:

1. **Remover Código Muerto** (1-2 horas)

   - Course UseCases (68% coverage, posible removable)
   - Unused helper methods
   - Benefit: Coverage improvement

2. **Mejorar Coverage** (2-3 horas)

   - Event state transitions edge cases
   - Course repository tests
   - Benefit: Coverage > 92%

3. **Documentación** (2-4 horas)
   - API examples (curl, Python client)
   - Architecture diagrams
   - Troubleshooting guide
   - Benefit: Better onboarding

---

**Última Actualización**: 3 de enero de 2026  
**Próxima Review**: Cuando se confirme roadmap de Q1
