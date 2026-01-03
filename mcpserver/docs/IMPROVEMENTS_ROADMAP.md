# Roadmap: Top 5 Mejoras para Redis Event Processing

## 📊 Overview Prioridades

```
Priority Matrix:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Impact
  ▲
  │     
  │  🔥 P0: Mejora #1   🔥 P0: Mejora #2
  │  ✅ DONE            ⏳ IN PROGRESS
  │  
  │  🎯 P1: Mejora #3   🛡️ P1: Mejora #5
  │  ⏳ TODO            ⏳ TODO
  │  
  │  📊 P2: Mejora #4
  │  ⏳ TODO
  │  
  └─────────────────────────────────────────► Complejidad
      Baja      Media      Alta
```

---

## 🎯 Mejora #1: Session Ownership Pattern ✅ COMPLETADA

**Estado**: ✅ DONE (commit `4bdb38d`)  
**Prioridad**: 🔥 P0 - Crítico  
**Impacto**: Alto - Previene resource leaks  
**Complejidad**: Baja  

### Qué se hizo
- ✅ Implementar `owns_session` en `AsyncSQLAlchemyUnitOfWork`
- ✅ Agregar verificación de estado con `_is_session_active()`
- ✅ Actualizar redis handler a `owns_session=False`
- ✅ Refactorizar tests para validar ambos escenarios
- ✅ Try/finally block para transacciones atomistas

### Beneficios
- 🛡️ Elimina double-close errors
- 🛡️ Claro quién posee la sesión
- 🛡️ Fácil de testear y mockear
- 🛡️ Graceful degradation

### Archivos Afectados
- `app/infrastructure/db/unit_of_work.py`
- `app/infrastructure/redis/main.py`
- `tests/unit/test_unit_of_work_unit.py`

---

## 🔥 Mejora #2: Publish Event to Processing Subject ⏳ NEXT

**Estado**: ⏳ TODO - Listo para implementar  
**Prioridad**: 🔥 P0 - Crítico  
**Impacto**: Alto - Desbloquea flujo evento → procesamiento → resultado  
**Complejidad**: Baja  

### Qué hacer
1. Después de enqueue exitoso → publicar a `processing-event-subject`
2. Incluir metadatos: `event_id`, `name`, `state`
3. Manejar errores permanentes (validation) vs transitorios

### Cambios Necesarios

**En** `handle_enqueue_event`:
```python
match result:
    case Ok(value):
        logger.info(f"Evento encolado: {value.id}")
        
        # ✅ NUEVO: Publicar al siguiente subject
        await broker.publish(
            {
                "event_id": str(value.id),
                "name": value.name,
                "state": value.state.value,
            },
            stream="processing-event-subject"
        )
        
        await msg.ack()
    case Err(error):
        if error.error == ErrorCatalog.VALIDATION_FAILED.value:
            await msg.ack()  # ✅ NO reintentar validaciones
        else:
            await msg.nack()  # ✅ Reintentar errores transitorios
```

### Tests Necesarios
```python
# tests/functional/test_redis_enqueue_handler.py

✅ test_enqueue_handler_happy_path
   - Mensaje válido → BD + publish a processing-subject + ack

✅ test_enqueue_handler_validation_error_acks_message
   - Error de validación → ack (NO nack)

✅ test_enqueue_handler_transient_error_nacks_message
   - Error transitorio → nack (reintentar)
```

### Archivos a Modificar
- `app/infrastructure/redis/main.py` (handle_enqueue_event)
- `tests/functional/test_redis_enqueue_handler.py` (new)

---

## 🎯 Mejora #3: MessagePublisher Gateway Pattern ⏳ P1

**Estado**: ⏳ TODO - Diseño listo  
**Prioridad**: 🎯 P1 - Importante  
**Impacto**: Medio - Abstracción limpia  
**Complejidad**: Media  

### Qué hacer
- Extraer lógica de publicación a interface `MessagePublisher`
- Crear adaptador `RedisMessagePublisher`
- Inyectar en handler vía `Depends(get_publisher)`
- Facilita swap de implementaciones (Redis → RabbitMQ, etc)

### Archivos a Crear/Modificar
```
app/
├── core/gateways/
│   └── message_publisher.py      (NEW)
├── infrastructure/redis/
│   ├── main.py                   (MODIFY)
│   └── publisher.py              (NEW)
tests/
└── unit/
    └── test_redis_publisher_unit.py (NEW)
```

### Estructura
```python
# app/core/gateways/message_publisher.py
class MessagePublisher(Protocol):
    async def publish_event_for_processing(
        self, event_id: UUID, name: str, state: str
    ) -> None: ...

# app/infrastructure/redis/publisher.py
class RedisMessagePublisher(MessagePublisher):
    def __init__(self, broker: RedisBroker, subject: str = "processing-event-subject"):
        self.broker = broker
        self.subject = subject

    async def publish_event_for_processing(self, event_id: UUID, name: str, state: str) -> None:
        await self.broker.publish(
            {"event_id": str(event_id), "name": name, "state": state},
            stream=self.subject
        )
```

---

## 🛡️ Mejora #5: Retry Policy + Dead Letter Queue ⏳ P1

**Estado**: ⏳ TODO - Diseño listo  
**Prioridad**: 🛡️ P1 - Importante  
**Impacto**: Alto - Robustez de producción  
**Complejidad**: Media  

### Qué hacer
1. Implementar max retries (ej: 3)
2. Crear dead-letter-queue para mensajes fallidos
3. Distinguir errores permanentes vs transitorios
4. Logging estructurado con contexto

### Configuración

```python
MAX_RETRIES = 3
DLQ_SUBJECT = "dead-letter-queue"

@EnqueueEventSubscriber
async def handle_enqueue_event(...):
    retry_count = msg.headers.get("retry_count", 0)
    
    match result:
        case Ok(value):
            # ✅ Success
            await msg.ack()
            
        case Err(error):
            if error.error == ErrorCatalog.VALIDATION_FAILED.value:
                # ✅ Permanent error → DLQ + ack
                await broker.publish(
                    {"event": event.model_dump(), "error": error.model_dump()},
                    stream=DLQ_SUBJECT
                )
                await msg.ack()
                
            elif retry_count >= MAX_RETRIES:
                # ✅ Too many retries → DLQ + ack
                await broker.publish(
                    {"event": event.model_dump(), "retries": retry_count},
                    stream=DLQ_SUBJECT
                )
                await msg.ack()
                
            else:
                # ✅ Transient error → nack (reintentar)
                await msg.nack()
```

### Tests Necesarios
```python
✅ test_enqueue_handler_max_retries_sends_to_dlq
   - 3 intentos fallidos → DLQ + ack

✅ test_enqueue_handler_validation_error_to_dlq
   - Error de validación → DLQ (no reintentar)
```

### Archivos a Crear/Modificar
- `app/infrastructure/redis/main.py` (MODIFY)
- `tests/functional/test_redis_enqueue_handler.py` (ADD tests)

---

## 📊 Mejora #4: Structured Logging ⏳ P2

**Estado**: ⏳ TODO - Opcional  
**Prioridad**: 📊 P2 - Nice to have  
**Impacto**: Medio - Observabilidad  
**Complejidad**: Baja  

### Qué hacer
- Usar `structlog` para logging estructurado
- Agregar correlation ID para trazabilidad
- Contexto: event_name, event_id, external_uuid, retry_count

### Ejemplo

```python
import structlog

logger = structlog.get_logger(__name__)

@EnqueueEventSubscriber
async def handle_enqueue_event(...):
    log = logger.bind(
        event_name=event.name,
        event_id=str(event.id),
        external_uuid=str(event.external_uuid),
        correlation_id=msg.message_id if hasattr(msg, 'message_id') else None
    )
    
    log.info("event_received")
    # ...
    log.info("event_enqueued_success", state=value.state.value)
```

### Beneficios
- 🔍 Trazabilidad end-to-end
- 📊 Análisis de logs con ELK/CloudWatch
- 🔗 Correlación de eventos
- 📈 Debugging más rápido

---

## 📈 Roadmap Temporal

```
Week 1 (Jan 3-10):
├── ✅ Mejora #1: Session ownership           (DONE)
├── ⏳ Mejora #2: Publish to processing       (IN PROGRESS)
└── ⏳ Mejora #5: Retry + DLQ                  (TODO)

Week 2 (Jan 10-17):
├── ⏳ Mejora #3: MessagePublisher gateway     (TODO)
└── ⏳ Mejora #4: Structured logging           (TODO)

Week 3+:
├── Enhancement: Event result processing
├── Enhancement: Webhook notifications
└── Enhancement: Event analytics
```

---

## 🎯 Métricas de Éxito

| Mejora | Coverage | Tests | Quality |
|--------|----------|-------|---------|
| #1 | 92.16% ✅ | 99 ✅ | ruff+mypy ✅ |
| #2 | 93%+ 🎯 | 103+ 🎯 | ruff+mypy 🎯 |
| #3 | 94%+ 🎯 | 108+ 🎯 | ruff+mypy 🎯 |
| #4 | 94%+ 🎯 | 108+ 🎯 | ruff+mypy 🎯 |
| #5 | 95%+ 🎯 | 113+ 🎯 | ruff+mypy 🎯 |

---

## 📝 Referencias

- Mejora #1 docs: [docs/IMPROVEMENTS_SESSION_OWNERSHIP.md](IMPROVEMENTS_SESSION_OWNERSHIP.md)
- Design patterns: [ARCHITECTURE_OPPORTUNITIES.md](ARCHITECTURE_OPPORTUNITIES.md)
- Development flow: [Agents.md](../Agents.md)
