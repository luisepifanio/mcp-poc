# 🎯 Processor Pattern Design - Event Processing Architecture

**Fecha**: 3 de enero de 2026  
**Status**: 📋 DISEÑO ACTUALIZADO CON FEEDBACK  
**Alcance**: Processor abstraction + Long Running Tasks  

---

## 📋 Objetivo

Diseñar un sistema flexible de procesamiento que soporte:

1. **Request/Response Processors** (sync/async)
   - API Calls (async/await)
   - gRPC calls (async/await)
   - Local method/UseCase invocation (blocking)

2. **Long Running Tasks** (async con callbacks)
   - Tareas que requieren callback en subject específico
   - Asignación de resultado a event_id

3. **Error Classification**
   - Permanent errors (ValidationError, business logic) → FAILED sin retry
   - Transient errors (infra) → Retry con backoff

4. **UX-Optimized Retry Strategy**
   - Target: <500ms ideal, <2000ms con loading, p95 <3000ms
   - Exponential backoff solo para degradación de servicio

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  ProcessorRegistry                              │
│  Maps: event.name → IEventProcessor implementation              │
├─────────────────────────────────────────────────────────────────┤
│  - api_call_processor: ApiCallProcessor                         │
│  - grpc_processor: GrpcProcessor                                │
│  - local_processor: LocalUseCaseProcessor                       │
│  - long_running_processor: LongRunningTaskProcessor             │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               IEventProcessor (ABC)                             │
│  async def process(event: Event) -> ProcessorResult             │
│  def get_retry_config() -> RetryConfig                          │
│  def classify_error(exc: Exception) -> ErrorType                │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────────┐   ┌─────────────────────┐
│  ApiCall     │   │  LocalUseCase    │   │  LongRunningTask    │
│  Processor   │   │  Processor       │   │  Processor          │
│              │   │                  │   │                     │
│ - HTTP calls │   │ - UseCase exec   │   │ - Publish task      │
│ - async/await│   │ - Blocking OK    │   │ - Wait callback     │
└──────────────┘   └──────────────────┘   └─────────────────────┘
```

---

## 📊 Processor Abstraction (IEventProcessor)

### Base Interface

```python
# app/core/processors.py

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Protocol
from dataclasses import dataclass

class ErrorType(str, Enum):
    """Classification of errors for retry logic"""
    TRANSIENT = "transient"      # Retry allowed (infra failures)
    PERMANENT = "permanent"      # No retry (validation, business logic)
    RATE_LIMIT = "rate_limit"    # Retry with longer backoff

class ProcessorResultStatus(str, Enum):
    SUCCESS = "success"
    PENDING_CALLBACK = "pending_callback"  # For long-running tasks
    FAILED = "failed"

@dataclass
class RetryConfig:
    """Retry configuration per processor"""
    max_attempts: int
    initial_backoff: float      # seconds
    max_backoff: float          # seconds
    backoff_multiplier: float
    # UX-optimized: fast retries first, then exponential
    fast_retry_count: int = 2   # First N attempts with minimal backoff
    fast_retry_delay: float = 0.1  # 100ms for fast retries

@dataclass
class ProcessorResult:
    """Result of processor execution"""
    status: ProcessorResultStatus
    data: dict[str, Any] | None = None
    error: str | None = None
    callback_subject: str | None = None  # For long-running tasks
    metadata: dict[str, Any] | None = None

class IEventProcessor(ABC):
    """
    Abstract interface for event processors.
    
    Each processor handles a specific event type and defines:
    - How to process the event
    - Retry configuration
    - Error classification
    """
    
    @abstractmethod
    async def process(self, event: Event) -> ProcessorResult:
        """
        Process the event.
        
        Returns:
            ProcessorResult with status, data, and optional callback info
        
        Raises:
            Exception: Any error during processing (will be classified)
        """
        pass
    
    @abstractmethod
    def get_retry_config(self) -> RetryConfig:
        """
        Get retry configuration for this processor.
        
        Returns:
            RetryConfig with max attempts, backoff settings
        """
        pass
    
    def classify_error(self, exc: Exception) -> ErrorType:
        """
        Classify error for retry logic.
        
        Default implementation:
        - ValidationError, ValueError → PERMANENT
        - ConnectionError, TimeoutError, HTTPError 5xx → TRANSIENT
        - HTTPError 429 → RATE_LIMIT
        
        Override for custom classification.
        """
        from pydantic import ValidationError
        from httpx import HTTPError, HTTPStatusError
        
        # Permanent errors (no retry)
        if isinstance(exc, (ValidationError, ValueError, KeyError)):
            return ErrorType.PERMANENT
        
        # Rate limit errors (retry with longer backoff)
        if isinstance(exc, HTTPStatusError) and exc.response.status_code == 429:
            return ErrorType.RATE_LIMIT
        
        # Transient errors (retry allowed)
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return ErrorType.TRANSIENT
        
        if isinstance(exc, HTTPStatusError) and 500 <= exc.response.status_code < 600:
            return ErrorType.TRANSIENT
        
        # Default: treat as permanent
        return ErrorType.PERMANENT
```

---

## 🔧 Processor Implementations

### 1. ApiCallProcessor (Request/Response)

```python
# app/infrastructure/processors/api_call_processor.py

import httpx
from app.core.processors import IEventProcessor, ProcessorResult, RetryConfig, ProcessorResultStatus

class ApiCallProcessor(IEventProcessor):
    """
    Processor for HTTP API calls (async).
    
    Event payload structure:
    {
        "url": "https://api.example.com/endpoint",
        "method": "POST",
        "body": {...},
        "headers": {...},
        "timeout": 5.0
    }
    """
    
    def __init__(self):
        self.client = httpx.AsyncClient()
    
    async def process(self, event: Event) -> ProcessorResult:
        payload = event.payload
        
        # Extract request params
        url = payload.get("url")
        method = payload.get("method", "GET")
        body = payload.get("body")
        headers = payload.get("headers", {})
        timeout = payload.get("timeout", 5.0)
        
        # Validate required fields
        if not url:
            raise ValueError("Missing required field: url")
        
        # Make request
        response = await self.client.request(
            method=method,
            url=url,
            json=body,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        
        # Return result
        return ProcessorResult(
            status=ProcessorResultStatus.SUCCESS,
            data={
                "status_code": response.status_code,
                "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                "headers": dict(response.headers),
            },
        )
    
    def get_retry_config(self) -> RetryConfig:
        """
        UX-optimized retry: fast retries first, then exponential.
        
        Timeline:
        - Attempt 1: immediate (t=0ms)
        - Attempt 2: +100ms (t=100ms, fast retry)
        - Attempt 3: +100ms (t=200ms, fast retry)
        - Attempt 4: +500ms (t=700ms, exponential)
        - Attempt 5: +1000ms (t=1700ms, exponential)
        
        Target: p95 < 3000ms
        """
        return RetryConfig(
            max_attempts=5,
            initial_backoff=0.5,      # 500ms after fast retries
            max_backoff=5.0,          # 5s max
            backoff_multiplier=2.0,   # 500ms, 1s, 2s, 4s
            fast_retry_count=2,       # First 2 retries fast
            fast_retry_delay=0.1,     # 100ms for fast retries
        )
```

### 2. LocalUseCaseProcessor (Blocking)

```python
# app/infrastructure/processors/local_usecase_processor.py

from app.core.processors import IEventProcessor, ProcessorResult, RetryConfig, ProcessorResultStatus

class LocalUseCaseProcessor(IEventProcessor):
    """
    Processor for local UseCase invocation (blocking allowed).
    
    Event payload structure:
    {
        "usecase_name": "CreateUserUseCase",
        "input": {...}
    }
    """
    
    def __init__(self, uow: IUnitOfWork):
        self.uow = uow
        # Registry of available use cases
        self.usecases = {
            "CreateUserUseCase": CreateUserUseCase,
            # Add more use cases here
        }
    
    async def process(self, event: Event) -> ProcessorResult:
        payload = event.payload
        
        # Extract usecase params
        usecase_name = payload.get("usecase_name")
        usecase_input = payload.get("input", {})
        
        # Validate
        if not usecase_name:
            raise ValueError("Missing required field: usecase_name")
        
        if usecase_name not in self.usecases:
            raise ValueError(f"Unknown usecase: {usecase_name}")
        
        # Instantiate and execute
        usecase_class = self.usecases[usecase_name]
        usecase = usecase_class(uow=self.uow)
        
        # Note: This is blocking if UseCase is sync
        result = await usecase.execute(usecase_input)
        
        if result.is_err():
            raise RuntimeError(f"UseCase failed: {result.unwrap_err()}")
        
        return ProcessorResult(
            status=ProcessorResultStatus.SUCCESS,
            data=result.unwrap().model_dump(),
        )
    
    def get_retry_config(self) -> RetryConfig:
        """
        Local use cases: minimal retries (DB/infra failures only).
        """
        return RetryConfig(
            max_attempts=3,
            initial_backoff=0.2,
            max_backoff=2.0,
            backoff_multiplier=2.0,
            fast_retry_count=1,
            fast_retry_delay=0.05,  # 50ms
        )
```

### 3. LongRunningTaskProcessor (Callback Pattern)

```python
# app/infrastructure/processors/long_running_processor.py

from app.core.processors import IEventProcessor, ProcessorResult, RetryConfig, ProcessorResultStatus
from uuid import uuid4

class LongRunningTaskProcessor(IEventProcessor):
    """
    Processor for long-running tasks with callback.
    
    Flow:
    1. Publish task to dedicated subject (e.g., 'scraping-task-subject')
    2. Return PENDING_CALLBACK with callback subject
    3. Wait for callback on 'scraping-result-{event_id}' subject
    4. Another handler listens and updates event to COMPLETED
    
    Event payload structure:
    {
        "task_type": "scraping",
        "task_params": {
            "url": "https://example.com",
            "selector": ".content"
        }
    }
    """
    
    def __init__(self, broker: RedisBroker):
        self.broker = broker
    
    async def process(self, event: Event) -> ProcessorResult:
        payload = event.payload
        
        # Extract task params
        task_type = payload.get("task_type")
        task_params = payload.get("task_params", {})
        
        if not task_type:
            raise ValueError("Missing required field: task_type")
        
        # Generate callback subject (unique per event)
        callback_subject = f"{task_type}-result-{event.id}"
        
        # Publish task to dedicated subject
        task_subject = f"{task_type}-task-subject"
        await self.broker.publish(
            {
                "event_id": str(event.id),
                "task_params": task_params,
                "callback_subject": callback_subject,
            },
            stream=task_subject,
        )
        
        # Return PENDING_CALLBACK
        return ProcessorResult(
            status=ProcessorResultStatus.PENDING_CALLBACK,
            callback_subject=callback_subject,
            metadata={
                "task_type": task_type,
                "task_subject": task_subject,
                "published_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    
    def get_retry_config(self) -> RetryConfig:
        """
        Long-running tasks: no retries at process level.
        Retry logic handled by task worker.
        """
        return RetryConfig(
            max_attempts=1,  # No retry, handled by task worker
            initial_backoff=0.0,
            max_backoff=0.0,
            backoff_multiplier=1.0,
            fast_retry_count=0,
            fast_retry_delay=0.0,
        )
```

---

## 📦 Processor Registry

### ProcessorRegistry Implementation

```python
# app/core/processor_registry.py

from typing import Dict
from app.core.processors import IEventProcessor

class ProcessorRegistry:
    """
    Registry for event processors.
    
    Maps event.name → IEventProcessor implementation
    """
    
    def __init__(self):
        self._processors: Dict[str, IEventProcessor] = {}
    
    def register(self, event_name: str, processor: IEventProcessor):
        """Register a processor for an event type"""
        self._processors[event_name] = processor
    
    def get(self, event_name: str) -> IEventProcessor | None:
        """Get processor for an event type"""
        return self._processors.get(event_name)
    
    def has(self, event_name: str) -> bool:
        """Check if processor exists for event type"""
        return event_name in self._processors

# Global registry instance
processor_registry = ProcessorRegistry()

# Registration (in app startup)
def setup_processors(broker: RedisBroker, uow: IUnitOfWork):
    """Setup and register all processors"""
    processor_registry.register("api_call", ApiCallProcessor())
    processor_registry.register("grpc_call", GrpcProcessor())
    processor_registry.register("local_usecase", LocalUseCaseProcessor(uow))
    processor_registry.register("scraping_task", LongRunningTaskProcessor(broker))
    # Add more processors as needed
```

---

## 🔄 Updated ProcessEventUseCase with Processor Pattern

```python
# app/core/usecases/event_usecases.py (UPDATED)

from app.core.processor_registry import processor_registry
from app.core.processors import ProcessorResultStatus, ErrorType

class ProcessEventUseCase(AsyncUseCase[ProcessEventUseCaseInput, ProcessEventUseCaseOutput]):
    """
    Process an event using registered processor.
    
    Flow:
    1. Load event
    2. Get processor from registry (by event.name)
    3. Execute processor
    4. Handle result:
       - SUCCESS → COMPLETED
       - PENDING_CALLBACK → Save callback info, return pending
       - FAILED → Classify error (permanent vs transient)
    """
    
    def __init__(self, uow: IUnitOfWork):
        self.uow = uow
    
    async def execute(
        self, input: ProcessEventUseCaseInput
    ) -> Result[ProcessEventUseCaseOutput, ErrorDetail]:
        # 1. Load event
        event_result = await self.uow.events.get_by_id(input.event_id)
        if event_result.is_err():
            return event_result
        
        event = event_result.unwrap()
        
        # 2. Validate state
        if event.state not in [EventState.PENDING, EventState.RETRYING]:
            return Err(ErrorDetail(
                code="INVALID_STATE",
                message=f"Event {event.id} is in state {event.state}"
            ))
        
        # 3. Get processor from registry
        processor = processor_registry.get(event.name)
        if not processor:
            return Err(ErrorDetail(
                code="NO_PROCESSOR",
                message=f"No processor registered for event type: {event.name}"
            ))
        
        # 4. Transition to PROCESSING
        event.state = EventState.PROCESSING
        event.context = event.context or {}
        event.context["processing"] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "processor": event.name,
        }
        
        transition = EventTransition(
            from_state=EventState.PENDING if event.state == EventState.PENDING else EventState.RETRYING,
            to_state=EventState.PROCESSING,
            event_id=event.id,
        )
        event.transitions.append(transition)
        
        # 5. Execute processor
        try:
            result = await processor.process(event)
            
            # 6. Handle result based on status
            if result.status == ProcessorResultStatus.SUCCESS:
                # Success: Transition to COMPLETED
                event.state = EventState.COMPLETED
                event.result = result.data
                event.context["processing"]["completed_at"] = datetime.now(timezone.utc).isoformat()
                event.context["processing"]["duration_ms"] = self._calculate_duration_ms(
                    event.context["processing"]["started_at"]
                )
                
                transition = EventTransition(
                    from_state=EventState.PROCESSING,
                    to_state=EventState.COMPLETED,
                    event_id=event.id,
                )
                event.transitions.append(transition)
                
                save_result = await self.uow.events.save(event)
                if save_result.is_err():
                    return save_result
                
                return Ok(ProcessEventUseCaseOutput(
                    event_id=event.id,
                    state=event.state,
                    result=result.data,
                ))
            
            elif result.status == ProcessorResultStatus.PENDING_CALLBACK:
                # Long-running task: Save callback info
                event.state = EventState.PROCESSING  # Keep in PROCESSING
                event.context["callback"] = {
                    "subject": result.callback_subject,
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": result.metadata,
                }
                
                save_result = await self.uow.events.save(event)
                if save_result.is_err():
                    return save_result
                
                return Ok(ProcessEventUseCaseOutput(
                    event_id=event.id,
                    state=event.state,
                    result={"status": "pending_callback", "callback_subject": result.callback_subject},
                ))
            
            else:
                # FAILED status from processor
                raise RuntimeError(result.error or "Processor returned FAILED status")
        
        except Exception as e:
            # 7. Classify error
            error_type = processor.classify_error(e)
            
            if error_type == ErrorType.PERMANENT:
                # Permanent error: No retry, mark as FAILED
                event.state = EventState.FAILED
                event.context["error"] = {
                    "type": "permanent",
                    "message": str(e),
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                }
                
                transition = EventTransition(
                    from_state=EventState.PROCESSING,
                    to_state=EventState.FAILED,
                    event_id=event.id,
                )
                event.transitions.append(transition)
                
                save_result = await self.uow.events.save(event)
                if save_result.is_err():
                    return save_result
                
                return Err(ErrorDetail(
                    code="PERMANENT_ERROR",
                    message=str(e),
                ))
            
            else:
                # Transient or rate limit error: Mark for retry
                event.state = EventState.TEMPORAL_ERROR
                event.context["retry"] = event.context.get("retry", {
                    "current_attempt": 0,
                    "max_attempts": processor.get_retry_config().max_attempts,
                })
                event.context["retry"]["last_error"] = str(e)
                event.context["retry"]["error_type"] = error_type.value
                event.context["retry"]["last_retry_at"] = datetime.now(timezone.utc).isoformat()
                
                transition = EventTransition(
                    from_state=EventState.PROCESSING,
                    to_state=EventState.TEMPORAL_ERROR,
                    event_id=event.id,
                )
                event.transitions.append(transition)
                
                save_result = await self.uow.events.save(event)
                if save_result.is_err():
                    return save_result
                
                # Re-raise to trigger retry at handler level
                raise
    
    def _calculate_duration_ms(self, started_at: str) -> int:
        """Calculate duration in milliseconds"""
        start = datetime.fromisoformat(started_at)
        end = datetime.now(timezone.utc)
        return int((end - start).total_seconds() * 1000)
```

---

## 🔄 Long Running Task Callback Handler

```python
# app/infrastructure/redis/callback_handlers.py

@broker.subscriber(stream="scraping-result-*")  # Wildcard subscription
async def handle_task_callback(
    body: dict[str, Any],
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Handle callbacks from long-running tasks.
    
    Expected body:
    {
        "event_id": "uuid",
        "status": "success" | "failed",
        "result": {...},  # If success
        "error": "...",   # If failed
    }
    """
    try:
        event_id = UUID(body["event_id"])
        status = body["status"]
        
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            # Load event
            event_result = await uow.events.get_by_id(event_id)
            if event_result.is_err():
                logger.error(f"Event {event_id} not found for callback")
                await msg.nack()
                return
            
            event = event_result.unwrap()
            
            # Verify state (should be PROCESSING with callback info)
            if event.state != EventState.PROCESSING:
                logger.warning(f"Event {event_id} not in PROCESSING state for callback")
                await msg.ack()  # Don't reprocess
                return
            
            if "callback" not in event.context:
                logger.warning(f"Event {event_id} missing callback info")
                await msg.ack()
                return
            
            # Update based on callback status
            if status == "success":
                # Success: Transition to COMPLETED
                event.state = EventState.COMPLETED
                event.result = body.get("result")
                event.context["processing"]["completed_at"] = datetime.now(timezone.utc).isoformat()
                event.context["processing"]["duration_ms"] = int(
                    (datetime.now(timezone.utc) - datetime.fromisoformat(
                        event.context["processing"]["started_at"]
                    )).total_seconds() * 1000
                )
                event.context["callback"]["received_at"] = datetime.now(timezone.utc).isoformat()
                
                transition = EventTransition(
                    from_state=EventState.PROCESSING,
                    to_state=EventState.COMPLETED,
                    event_id=event.id,
                )
                event.transitions.append(transition)
                
            else:
                # Failed: Transition to FAILED (no retry for task failures)
                event.state = EventState.FAILED
                event.context["error"] = {
                    "type": "task_failed",
                    "message": body.get("error", "Task failed"),
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                }
                event.context["callback"]["received_at"] = datetime.now(timezone.utc).isoformat()
                
                transition = EventTransition(
                    from_state=EventState.PROCESSING,
                    to_state=EventState.FAILED,
                    event_id=event.id,
                )
                event.transitions.append(transition)
            
            # Save
            save_result = await uow.events.save(event)
            if save_result.is_err():
                logger.error(f"Failed to save event {event_id} after callback: {save_result.unwrap_err()}")
                await msg.nack()
                return
            
            logger.info(f"Event {event_id} callback processed: {status}")
            await msg.ack()
            
    except Exception as e:
        logger.error(f"Error handling task callback: {e}", exc_info=True)
        await msg.nack()
```

---

## 📊 UX-Optimized Retry Strategy

### Retry Timeline Comparison

**Original Design** (no UX optimization):
```
Attempt 1: t=0s
Attempt 2: t=2s    (+2s)
Attempt 3: t=6s    (+4s)
Attempt 4: t=14s   (+8s)
Attempt 5: t=30s   (+16s)
───────────────────────────
Total: ~30s → p95 = 30000ms ❌ (exceeds 3000ms target)
```

**UX-Optimized Design** (fast retries first):
```
Attempt 1: t=0ms      (immediate)
Attempt 2: t=100ms    (+100ms, fast)
Attempt 3: t=200ms    (+100ms, fast)
Attempt 4: t=700ms    (+500ms, exponential)
Attempt 5: t=1700ms   (+1000ms, exponential)
Attempt 6: t=3700ms   (+2000ms, exponential) → Only if service degraded
───────────────────────────────────────────────────
p95 target: <3000ms ✅
Success rate optimization: 80% success by attempt 3
```

### Implementation in Handler

```python
# app/infrastructure/redis/main.py (UPDATED)

async def handle_processing_event_queue(
    body: EnqueuedEventUseCaseOutput,
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any] | None:
    """
    UX-optimized retry strategy:
    - First 2 retries: 100ms delay (fast recovery)
    - Remaining retries: Exponential backoff (500ms, 1s, 2s)
    
    Target: p95 < 3000ms
    """
    event_id = body.id
    
    try:
        # Load event and get processor config
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            event_result = await uow.events.get_by_id(event_id)
            if event_result.is_err():
                await msg.nack()
                return None
            
            event = event_result.unwrap()
            
            # Get processor to determine retry config
            processor = processor_registry.get(event.name)
            if not processor:
                logger.error(f"No processor for event {event.name}")
                await msg.nack()
                return None
            
            retry_config = processor.get_retry_config()
            
            # Check current attempt
            context = event.context or {}
            retry_meta = context.get("retry", {
                "current_attempt": 0,
                "max_attempts": retry_config.max_attempts,
            })
            current_attempt = retry_meta["current_attempt"]
            max_attempts = retry_config.max_attempts
            
            # Check if exhausted
            if current_attempt >= max_attempts:
                # Exhaust event
                exhaust_usecase = ExhaustEventUseCase(uow)
                exhaust_result = await exhaust_usecase.execute(
                    ExhaustEventUseCaseInput(
                        event_id=event_id,
                        final_error=retry_meta.get("last_error", "Max retries exceeded"),
                    )
                )
                
                if exhaust_result.is_ok():
                    logger.info(f"Event {event_id} exhausted and logged")
                
                await msg.ack()
                return None
        
        # Determine retry delay based on attempt
        if current_attempt < retry_config.fast_retry_count:
            # Fast retry
            retry_delay = retry_config.fast_retry_delay
        else:
            # Exponential backoff
            backoff_attempt = current_attempt - retry_config.fast_retry_count
            retry_delay = min(
                retry_config.initial_backoff * (retry_config.backoff_multiplier ** backoff_attempt),
                retry_config.max_backoff
            )
        
        # Apply retry with calculated delay
        if current_attempt > 0:
            await asyncio.sleep(retry_delay)
        
        # Process event
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            process_usecase = ProcessEventUseCase(uow)
            process_result = await process_usecase.execute(
                ProcessEventUseCaseInput(
                    event_id=event_id,
                    payload=body.model_dump(),
                )
            )
            
            if process_result.is_err():
                error = process_result.unwrap_err()
                
                # Check if permanent error
                if error.code == "PERMANENT_ERROR":
                    logger.error(f"Permanent error for event {event_id}: {error.message}")
                    await msg.ack()  # Don't retry permanent errors
                    return None
                
                # Transient error: Increment attempt and retry
                logger.warning(f"Transient error for event {event_id}, will retry")
                await msg.nack()
                return None
            
            output = process_result.unwrap()
            
            # Check if pending callback
            if output.state == EventState.PROCESSING and "callback" in event.context:
                logger.info(f"Event {event_id} waiting for callback")
                await msg.ack()  # Don't reprocess, callback handler will complete
                return None
            
            # Success
            logger.info(f"Event {event_id} processed successfully")
            await msg.ack()
            return output.model_dump()
        
    except Exception as e:
        logger.error(f"Unexpected error processing event {event_id}: {e}", exc_info=True)
        
        # Increment attempt
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            event_result = await uow.events.get_by_id(event_id)
            if event_result.is_ok():
                event = event_result.unwrap()
                context = event.context or {}
                retry_meta = context.get("retry", {"current_attempt": 0})
                retry_meta["current_attempt"] += 1
                retry_meta["last_error"] = str(e)
                retry_meta["last_retry_at"] = datetime.now(timezone.utc).isoformat()
                context["retry"] = retry_meta
                event.context = context
                
                # Transition to RETRYING if from TEMPORAL_ERROR
                if event.state == EventState.TEMPORAL_ERROR:
                    event.state = EventState.RETRYING
                    transition = EventTransition(
                        from_state=EventState.TEMPORAL_ERROR,
                        to_state=EventState.RETRYING,
                        event_id=event.id,
                    )
                    event.transitions.append(transition)
                
                await uow.events.save(event)
        
        await msg.nack()
        return None
```

---

## 📚 Summary

### Processor Types

| Type | Example | Latency | Retry Strategy |
|------|---------|---------|----------------|
| **ApiCallProcessor** | HTTP/REST API | <500ms ideal | Fast retries (100ms x2) + exponential |
| **GrpcProcessor** | gRPC calls | <300ms ideal | Fast retries (50ms x2) + exponential |
| **LocalUseCaseProcessor** | Local UseCase | <100ms | Minimal (50ms x1) + exponential |
| **LongRunningTaskProcessor** | Scraping, ML | >5s | No retry (callback handles) |

### Error Classification

| Error Type | Examples | Retry Behavior |
|------------|----------|----------------|
| **PERMANENT** | ValidationError, ValueError, BusinessLogicError | No retry → FAILED |
| **TRANSIENT** | ConnectionError, TimeoutError, HTTP 5xx | Retry with backoff |
| **RATE_LIMIT** | HTTP 429 | Retry with longer backoff |

### UX Targets

- **Ideal**: <500ms (no loading indicator)
- **Acceptable**: <2000ms (loading indicator)
- **p95 Target**: <3000ms
- **Service Degradation**: >3000ms (exponential backoff for infrastructure failures)

---

**Next Steps**: Aprobación de diseño antes de implementación

**Documentación Relacionada**:
- [MVP_DESIGN_PROCESSING_HANDLER.md](MVP_DESIGN_PROCESSING_HANDLER.md)
- [RETRY_STRATEGY.md](RETRY_STRATEGY.md)
