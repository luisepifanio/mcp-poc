# 🎯 MVP Design - Reformulado con Feedback Integrado

**Fecha**: 3 de enero de 2026  
**Status**: 📋 DISEÑO REFORMULADO V2  
**Cambios**: Event states, Topic strategy, Processor registry, NoOp detector  

---

## 📋 Decisiones Clave

### 1. EventState Analysis: WAITING_CALLBACK vs PROCESSING

**Conclusión**: **No es necesario WAITING_CALLBACK** 

**Rationale**:
- PROCESSING ya cubre ambos casos (sync request/response Y async callback)
- La diferencia es en **metadata dentro de Event.context**, no en el estado
- PROCESSING → COMPLETED aplica para ambos (solo cambia timing)
- Metadata diferencia:
  - **Sync**: `context.processing.completed_at` inmediato
  - **Async**: `context.callback.subject` + esperando callback

**Decision**: Mantener PROCESSING como estado único. El tipo de procesamiento (sync/async) es metadata en `context`.

```python
# SYNC (ApiCall, LocalUseCase)
event.state = PROCESSING
event.context = {
    "processing": {
        "started_at": "2026-01-03T10:00:00Z",
        "processor": "api_call",
        "type": "sync"  # ← Diferencia
    }
}
# Luego → COMPLETED inmediatamente

# ASYNC (LongRunningTask)
event.state = PROCESSING
event.context = {
    "processing": {
        "started_at": "2026-01-03T10:00:00Z",
        "processor": "scraping_task",
        "type": "async_callback"  # ← Diferencia
    },
    "callback": {
        "subject": "event-result-{event_id}",
        "task_subject": "scraping-task-subject",
        "published_at": "2026-01-03T10:00:00Z"
    }
}
# Luego → COMPLETED cuando llega callback
```

**Estados Finales**:
```
CREATED → PENDING → PROCESSING → COMPLETED/FAILED/EXHAUSTED
                         ↓
                   TEMPORAL_ERROR
                         ↓
                   RETRYING
```

---

### 2. Topic Strategy: Unificado + Dinámico

**Nuevo Modelo**:

```
Task Subject (Configurable por Processor):
  "scraping-task-subject"
  "ml-inference-subject"
  "batch-export-subject"
  (cada processor define su own task topic)
        │
        ▼
    Worker procesa
        │
        ▼
Result Subject (UNIFICADO):
  "event-result-{event_id}"
  (same para todos)
  
Ventaja: 
- Callbacks siempre en mismo patrón
- No wildcard subscribers (mejor performance)
- Facilita monitoreo (all results en patrón predecible)
```

**Redis Setup**:
```python
# Task subjects (uno por processor type)
SCRAPING_TASK_SUBJECT = "scraping-task-subject"
ML_INFERENCE_SUBJECT = "ml-inference-subject"

# Result subjects (unificado)
def get_event_result_subject(event_id: UUID) -> str:
    return f"event-result-{event_id}"

# NO wildcards, solo subscribe específicamente
@broker.subscriber(stream=f"event-result-{event_id}")  # Per-event subscription
async def handle_task_callback(...)
```

**¿Dynamic Topics Overhead?**
- Redis Streams: Crear topic dinámico ~0ms (es lazy-create)
- No hay overhead significativo
- Decisión: **SÍ usar dynamic topics por evento**

---

### 3. Callback Payload: BaseModel vs TypedDict

**Decision**: **BaseModel para callbacks** (más type-safe)

**Rationale**:
- Pydantic validation automática
- Serializable directo
- Compatible con Event.result (EventResultStructure)
- Mejor para testing

```python
# Callback payload (BaseModel)
class TaskCallbackPayload(BaseModel):
    """Unified callback structure for all processors"""
    event_id: UUID
    status: str  # "success" | "failed"
    result: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None  # task-specific metadata

# Uso en handler
@broker.subscriber(stream=f"event-result-*")  # Dynamic per-event
async def handle_task_callback(
    body: TaskCallbackPayload,  # Pydantic auto-validates
    msg: RedisMessage,
)
```

---

### 4. NoOpProcessor: Detección de Eventos No Catalogados

**Objetivo**: Detectar y monitorear eventos sin processor activo

**Implementation**:

```python
class NoOpProcessor(IEventProcessor):
    """
    Default processor for events without explicit handler.
    
    Marks event as FAILED (not retryable) with monitoring info.
    Purpose: Catch new event types that haven't been added to catalog.
    """
    
    async def process(self, event: Event) -> ProcessorResult:
        # Log for monitoring
        logger.warning(
            f"NoOpProcessor handling event: {event.name}",
            extra={
                "event_id": str(event.id),
                "event_name": event.name,
                "payload_keys": list(event.payload.keys()) if event.payload else [],
            }
        )
        
        raise ValueError(f"No processor registered for event type: {event.name}")
    
    def get_retry_config(self) -> RetryConfig:
        # No retries for missing processor
        return RetryConfig(
            max_attempts=1,
            initial_backoff=0.0,
            max_backoff=0.0,
            backoff_multiplier=1.0,
            fast_retry_count=0,
            fast_retry_delay=0.0,
        )
    
    def classify_error(self, exc: Exception) -> ErrorType:
        # Always permanent - no processor found
        return ErrorType.PERMANENT
```

**ProcessorRegistry Update**:

```python
class ProcessorRegistry:
    def __init__(self):
        self._processors: Dict[str, IEventProcessor] = {}
        self._noop_processor = NoOpProcessor()  # Default fallback
    
    def get(self, event_name: str) -> IEventProcessor:
        """Get processor, default to NoOpProcessor if not found"""
        processor = self._processors.get(event_name)
        
        if processor is None:
            logger.warning(
                f"Processor not found for event type: {event_name}, using NoOpProcessor"
            )
            return self._noop_processor
        
        return processor
```

**Benefits**:
- ✅ Detecta automáticamente nuevos event types
- ✅ Log estructurado para monitoreo
- ✅ No rompe pipeline (FAILED gracefully)
- ✅ Facilita onboarding de nuevos event types

---

## 🏗️ Architecture Diagram (Reformulado)

```
┌─────────────────────────────────────────────────────────────┐
│                    ProcessorRegistry                         │
│  Maps: event.name → IEventProcessor implementation           │
│  + NoOpProcessor como fallback para unregistered events      │
├─────────────────────────────────────────────────────────────┤
│ • api_call_processor                                        │
│ • grpc_processor                                            │
│ • local_processor                                           │
│ • scraping_processor → task_subject: "scraping-task"       │
│ • ml_inference_processor → task_subject: "ml-inference"    │
│ • [NoOpProcessor] (fallback for unknown events)            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  ProcessEventUseCase │
        │  + Error Classifier  │
        │  + Retry Logic       │
        └──────────┬───────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  ┌──────────────┐    ┌──────────────────┐
  │ SYNC Proc    │    │ ASYNC Proc       │
  │ (ApiCall)    │    │ (LongRunning)    │
  │              │    │                  │
  │ Return       │    │ Publish to:      │
  │ COMPLETED    │    │ - "scraping-...  │
  │ immediately  │    │ - "ml-inference" │
  └──────────────┘    │ Return           │
                      │ PENDING_CALLBACK │
                      └────────┬─────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │ Worker Process  │
                        │ (External/Async)│
                        │                 │
                        │ Publish result  │
                        │ to:             │
                        │ "event-result-" │
                        │ "{event_id}"    │
                        └────────┬────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ handle_task_callback   │
                    │ (Single handler)       │
                    │                        │
                    │ Validated by Pydantic  │
                    │ Payload:               │
                    │ - event_id             │
                    │ - status               │
                    │ - result/error         │
                    │                        │
                    │ Update Event:          │
                    │ state → COMPLETED      │
                    └────────────────────────┘
```

---

## 🔧 Implementación Reformulada

### 1. Core Types

```python
# app/core/processors.py

from enum import Enum
from typing import Any
from dataclasses import dataclass
from pydantic import BaseModel

class ErrorType(str, Enum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    RATE_LIMIT = "rate_limit"

class ProcessorResultStatus(str, Enum):
    SUCCESS = "success"
    PENDING_CALLBACK = "pending_callback"
    FAILED = "failed"

@dataclass
class RetryConfig:
    max_attempts: int
    initial_backoff: float
    max_backoff: float
    backoff_multiplier: float
    fast_retry_count: int = 2
    fast_retry_delay: float = 0.1

@dataclass
class ProcessorResult:
    status: ProcessorResultStatus
    data: dict[str, Any] | None = None
    error: str | None = None
    callback_subject: str | None = None  # Only for PENDING_CALLBACK
    metadata: dict[str, Any] | None = None

class IEventProcessor(ABC):
    @abstractmethod
    async def process(self, event: Event) -> ProcessorResult:
        pass
    
    @abstractmethod
    def get_retry_config(self) -> RetryConfig:
        pass
    
    def classify_error(self, exc: Exception) -> ErrorType:
        # Default implementation
        from pydantic import ValidationError
        if isinstance(exc, (ValidationError, ValueError)):
            return ErrorType.PERMANENT
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return ErrorType.TRANSIENT
        return ErrorType.PERMANENT
```

### 2. Task Callback Payload (Unified Pydantic Model)

```python
# app/infrastructure/processors/callbacks.py

from pydantic import BaseModel
from typing import Any
from uuid import UUID

class TaskCallbackPayload(BaseModel):
    """
    Unified callback structure for all long-running processors.
    
    Published to: "event-result-{event_id}" (dynamic, per event)
    """
    event_id: UUID
    status: str  # "success" | "failed"
    result: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None  # Processor-specific data
    
    # Auto-trim extra fields for flexible extensibility
    class Config:
        extra = "allow"

# Processor-specific payloads (inherit from TaskCallbackPayload if needed)
class ScrapingTaskCallbackPayload(TaskCallbackPayload):
    """Specific to scraping processor"""
    metadata: dict[str, Any] | None = {
        "url": str,
        "selector_count": int,
        "duration_ms": int,
    }

class MlInferenceCallbackPayload(TaskCallbackPayload):
    """Specific to ML inference processor"""
    metadata: dict[str, Any] | None = {
        "model_id": str,
        "confidence": float,
        "inference_ms": int,
    }
```

### 3. LongRunningTaskProcessor (Updated)

```python
# app/infrastructure/processors/long_running_processor.py

from app.core.processors import IEventProcessor, ProcessorResult, RetryConfig

class LongRunningTaskProcessor(IEventProcessor):
    """
    Base class for long-running processors.
    
    Subclasses define:
    - task_subject: Topic where task is published
    - Example: ScrapingProcessor → "scraping-task-subject"
    """
    
    def __init__(self, broker: RedisBroker, task_subject: str):
        self.broker = broker
        self.task_subject = task_subject
    
    async def process(self, event: Event) -> ProcessorResult:
        """
        Publish task and return PENDING_CALLBACK.
        
        Flow:
        1. Validate task params
        2. Publish to task_subject (e.g., "scraping-task-subject")
        3. Return PENDING_CALLBACK with callback_subject="event-result-{event_id}"
        """
        
        callback_subject = f"event-result-{event.id}"
        
        # Publish task (format depends on processor)
        task_payload = {
            "event_id": str(event.id),
            "task_params": event.payload,
            "callback_subject": callback_subject,
        }
        
        await self.broker.publish(
            task_payload,
            stream=self.task_subject,
        )
        
        return ProcessorResult(
            status=ProcessorResultStatus.PENDING_CALLBACK,
            callback_subject=callback_subject,
            metadata={
                "task_subject": self.task_subject,
                "published_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    
    def get_retry_config(self) -> RetryConfig:
        # No retries for long-running tasks
        return RetryConfig(
            max_attempts=1,
            initial_backoff=0.0,
            max_backoff=0.0,
            backoff_multiplier=1.0,
            fast_retry_count=0,
            fast_retry_delay=0.0,
        )


# Specific implementations
class ScrapingProcessor(LongRunningTaskProcessor):
    def __init__(self, broker: RedisBroker):
        super().__init__(broker, task_subject="scraping-task-subject")


class MlInferenceProcessor(LongRunningTaskProcessor):
    def __init__(self, broker: RedisBroker):
        super().__init__(broker, task_subject="ml-inference-subject")
```

### 4. ProcessorRegistry with NoOpProcessor

```python
# app/core/processor_registry.py

from typing import Dict
import logging

logger = logging.getLogger(__name__)

class NoOpProcessor(IEventProcessor):
    """
    Default processor for unregistered event types.
    Detects and monitors new event types without explicit handler.
    """
    
    async def process(self, event: Event) -> ProcessorResult:
        logger.warning(
            f"NoOpProcessor: Event without registered processor",
            extra={
                "event_id": str(event.id),
                "event_name": event.name,
                "payload_keys": list(event.payload.keys()) if event.payload else [],
            }
        )
        
        raise ValueError(
            f"No processor registered for event type: {event.name}. "
            "Add to ProcessorRegistry or update catalog configuration."
        )
    
    def get_retry_config(self) -> RetryConfig:
        # No retries - permanent error
        return RetryConfig(
            max_attempts=1,
            initial_backoff=0.0,
            max_backoff=0.0,
            backoff_multiplier=1.0,
            fast_retry_count=0,
            fast_retry_delay=0.0,
        )
    
    def classify_error(self, exc: Exception) -> ErrorType:
        # Always permanent - no processor found is not retryable
        return ErrorType.PERMANENT


class ProcessorRegistry:
    """
    Registry for event processors.
    Uses NoOpProcessor as fallback for unregistered event types.
    """
    
    def __init__(self):
        self._processors: Dict[str, IEventProcessor] = {}
        self._noop = NoOpProcessor()
    
    def register(self, event_name: str, processor: IEventProcessor):
        """Register processor for event type"""
        logger.info(f"Registered processor for event type: {event_name}")
        self._processors[event_name] = processor
    
    def get(self, event_name: str) -> IEventProcessor:
        """
        Get processor for event type.
        Returns NoOpProcessor if not found (detects new event types).
        """
        processor = self._processors.get(event_name)
        
        if processor is None:
            logger.warning(
                f"Processor not found for event type: {event_name}, "
                f"using NoOpProcessor (will mark as FAILED)",
                extra={"event_name": event_name}
            )
            return self._noop
        
        return processor
    
    def has(self, event_name: str) -> bool:
        """Check if explicit processor registered (excludes NoOp)"""
        return event_name in self._processors


# Global instance
processor_registry = ProcessorRegistry()


def setup_processors(broker: RedisBroker, uow: IUnitOfWork):
    """Setup and register all processors"""
    # Sync processors
    processor_registry.register("api_call", ApiCallProcessor())
    processor_registry.register("grpc_call", GrpcProcessor())
    processor_registry.register("local_usecase", LocalUseCaseProcessor(uow))
    
    # Async long-running processors
    processor_registry.register("scraping_task", ScrapingProcessor(broker))
    processor_registry.register("ml_inference", MlInferenceProcessor(broker))
    
    # NoOpProcessor is implicit fallback (no registration needed)
    logger.info("Processor registry initialized")
```

### 5. Unified Task Callback Handler

```python
# app/infrastructure/redis/callback_handlers.py

from app.infrastructure.processors.callbacks import TaskCallbackPayload

@broker.subscriber(stream="event-result-*")  # Dynamic per-event
async def handle_task_callback(
    body: TaskCallbackPayload,  # Pydantic validated
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Unified callback handler for all long-running processors.
    
    Listens on: "event-result-{event_id}" (dynamic topics)
    Payload: TaskCallbackPayload (validated by Pydantic)
    
    Updates event state based on callback status.
    """
    try:
        event_id = body.event_id
        status = body.status
        
        logger.info(
            f"Task callback received for event {event_id}: {status}",
            extra={
                "event_id": str(event_id),
                "status": status,
                "has_error": body.error is not None,
            }
        )
        
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            # Load event
            event_result = await uow.events.get_by_id(event_id)
            if event_result.is_err():
                logger.error(f"Event {event_id} not found for callback")
                await msg.nack()
                return
            
            event = event_result.unwrap()
            
            # Verify state (must be PROCESSING with callback metadata)
            if event.state != EventState.PROCESSING:
                logger.warning(
                    f"Event {event_id} not in PROCESSING state for callback",
                    extra={"event_state": event.state}
                )
                await msg.ack()  # Don't reprocess
                return
            
            # Update based on callback status
            if status == "success":
                # Success: Transition PROCESSING → COMPLETED
                event.state = EventState.COMPLETED
                event.result = body.result
                
                # Update processing metadata
                if "processing" not in event.context:
                    event.context["processing"] = {}
                event.context["processing"]["completed_at"] = datetime.now(timezone.utc).isoformat()
                event.context["processing"]["duration_ms"] = int(
                    (datetime.now(timezone.utc) - datetime.fromisoformat(
                        event.context["processing"]["started_at"]
                    )).total_seconds() * 1000
                )
                
                # Record callback reception
                if "callback" not in event.context:
                    event.context["callback"] = {}
                event.context["callback"]["received_at"] = datetime.now(timezone.utc).isoformat()
                event.context["callback"]["status"] = "success"
                if body.metadata:
                    event.context["callback"]["metadata"] = body.metadata
                
                # Add transition
                transition = EventTransition(
                    from_state=EventState.PROCESSING,
                    to_state=EventState.COMPLETED,
                    event_id=event.id,
                )
                event.transitions.append(transition)
                
                logger.info(f"Event {event_id} completed via callback")
                
            else:
                # Failed: Transition PROCESSING → FAILED (no retry for task failures)
                event.state = EventState.FAILED
                
                # Record error
                if "error" not in event.context:
                    event.context["error"] = {}
                event.context["error"]["type"] = "task_failed"
                event.context["error"]["message"] = body.error or "Task failed"
                event.context["error"]["occurred_at"] = datetime.now(timezone.utc).isoformat()
                
                # Record callback reception
                if "callback" not in event.context:
                    event.context["callback"] = {}
                event.context["callback"]["received_at"] = datetime.now(timezone.utc).isoformat()
                event.context["callback"]["status"] = "failed"
                if body.metadata:
                    event.context["callback"]["metadata"] = body.metadata
                
                # Add transition
                transition = EventTransition(
                    from_state=EventState.PROCESSING,
                    to_state=EventState.FAILED,
                    event_id=event.id,
                )
                event.transitions.append(transition)
                
                logger.error(
                    f"Event {event_id} failed via callback: {body.error}",
                    extra={"event_id": str(event_id), "error": body.error}
                )
            
            # Save event
            save_result = await uow.events.save(event)
            if save_result.is_err():
                logger.error(
                    f"Failed to save event {event_id} after callback",
                    extra={"event_id": str(event_id)}
                )
                await msg.nack()
                return
            
            # Success: ack message
            await msg.ack()
            
    except Exception as e:
        logger.error(
            f"Unexpected error in task callback handler: {e}",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        await msg.nack()
```

---

## 📊 Event Context Structure (Reformulado)

```python
class EventProcessingContext(TypedDict):
    """Tracking for SYNC processors"""
    retry: NotRequired[RetryMetadata]
    processing: NotRequired[ProcessingMetadata]  # started_at, completed_at, duration_ms, processor, type
    error: NotRequired[ErrorMetadata]
    exhausted: NotRequired[ExhaustedMetadata]


class EventCallbackContext(TypedDict):
    """Additional tracking for ASYNC (long-running) processors"""
    callback: NotRequired[CallbackMetadata]  # subject, task_subject, published_at, received_at, status, metadata
```

**Ejemplo SYNC (ApiCall)**:
```json
{
  "processing": {
    "started_at": "2026-01-03T10:00:00Z",
    "completed_at": "2026-01-03T10:00:100Z",
    "duration_ms": 100,
    "processor": "api_call",
    "type": "sync"
  }
}
```

**Ejemplo ASYNC (Scraping)**:
```json
{
  "processing": {
    "started_at": "2026-01-03T10:00:00Z",
    "processor": "scraping_task",
    "type": "async_callback"
  },
  "callback": {
    "subject": "event-result-{event_id}",
    "task_subject": "scraping-task-subject",
    "published_at": "2026-01-03T10:00:01Z",
    "received_at": "2026-01-03T10:05:30Z",
    "status": "success",
    "metadata": {
      "url": "https://...",
      "selector_count": 42,
      "duration_ms": 5000
    }
  }
}
```

---

## ✅ Cambios Resumidos vs Original

| Aspecto | Original | Reformulado | Beneficio |
|---------|----------|-------------|----------|
| **Event States** | PROCESSING + WAITING_CALLBACK | Solo PROCESSING (+ metadata) | Simplificación, menos estados |
| **Topics** | Wildcard subscribers | Dynamic "event-result-{event_id}" | Mejor performance, menos overhead |
| **Callback Payload** | TypedDict | Pydantic BaseModel | Validación automática, type-safe |
| **NoProcessor** | ❌ Falla silenciosa | ✅ NoOpProcessor + logging | Detección automática de nuevos eventos |
| **Task Topics** | "scraping-result-*" | "scraping-task-subject" (configurable) | Flexibilidad, clara separación |

---

## 🧪 Testing Strategy

**New tests for NoOpProcessor**:
```python
async def test_noop_processor_detects_unregistered_event(uow_mock):
    event = Event(name="unknown_event_type", ...)
    processor = processor_registry.get("unknown_event_type")
    
    # Should return NoOpProcessor
    assert isinstance(processor, NoOpProcessor)
    
    # Should fail with permanent error
    with pytest.raises(ValueError):
        await processor.process(event)

async def test_callback_handler_with_pydantic_validation(msg):
    # Pydantic validates payload automatically
    callback = TaskCallbackPayload(
        event_id=uuid4(),
        status="success",
        result={"data": "..."}
    )
    # Payload is already validated
```

---

## 🎯 Flujo Completo (Reformulado)

```
1. Event encolado (CREATED → PENDING)
   └─ Publicado a "processing-event-subject"

2. handle_processing_event_queue
   └─ Get processor from registry
      ├─ If not found → NoOpProcessor (logs warning)
      └─ Processor exists → execute

3. Processor execution
   ├─ SYNC (ApiCall):
   │  ├─ Execute request
   │  ├─ Return SUCCESS
   │  └─ event.state → COMPLETED (immediate)
   │
   └─ ASYNC (LongRunning):
      ├─ Validate task params
      ├─ Publish to task_subject ("scraping-task-subject")
      ├─ Return PENDING_CALLBACK
      │  └─ callback_subject = "event-result-{event_id}"
      └─ event.state → PROCESSING (waiting for callback)

4. External Worker
   ├─ Subscribe to task_subject
   ├─ Process task
   └─ Publish callback to "event-result-{event_id}"
      └─ Payload: TaskCallbackPayload (Pydantic validated)

5. handle_task_callback
   ├─ Validate payload (Pydantic)
   ├─ Load event (must be PROCESSING)
   ├─ Update state:
   │  ├─ If success → COMPLETED
   │  └─ If failed → FAILED (no retry)
   └─ Save event + ack message
```

---

## 🚀 Próximos Pasos

1. **Aprobación**: ¿Se aprueba la reformulación?
2. **Implementación**: Comenzar con core abstractions (IEventProcessor, NoOpProcessor, ProcessorRegistry)
3. **Testing**: Criar tests para cada processor
4. **Integration**: Integrar en handle_processing_event_queue y handle_task_callback

---

**Cambios principales**:

✅ Sin WAITING_CALLBACK (metadata en context)  
✅ Topics dinámicos unificados (event-result-{event_id})  
✅ Pydantic BaseModel para callbacks  
✅ NoOpProcessor para detectar eventos no catalogados  
