# 🎯 MVP Design: Processing Handler con Retry Strategy + DLQ

**Fecha**: 3 de enero de 2026  
**Status**: 📋 DISEÑO PARA REVISIÓN  
**Alcance**: Opción B - MVP (Mejora #3 + #5)

---

## 📋 Objetivo

Diseñar e implementar `handle_processing_event_queue` con:

1. **Transiciones de estado robustas**: PROCESSING → RETRYING → EXHAUSTED/COMPLETED
2. **Retry strategy con exponential backoff** (usando tenacity existente)
3. **Dead Letter Queue (DLQ)** para eventos irrecuperables
4. **Tracking estructurado** en `Event.context` (TypedDict)
5. **Tests exhaustivos** (unitarios + funcionales)

---

## 🏗️ Arquitectura Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  enqueue-event-subject (FASE 1-5 COMPLETADA)                    │
│  └─ handle_enqueue_event                                        │
│     ├─ Save Event (state: PENDING)                              │
│     └─ Publish → processing-event-subject                       │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  processing-event-subject (MVP - A IMPLEMENTAR)                 │
│  └─ handle_processing_event_queue                               │
│     ├─ Transition: PENDING → PROCESSING                         │
│     ├─ Execute business logic (simulated)                       │
│     ├─ On Success:                                              │
│     │  ├─ Transition: PROCESSING → COMPLETED                    │
│     │  ├─ Publish → result-event-subject                        │
│     │  └─ ack()                                                 │
│     ├─ On Transient Error (retry < max):                        │
│     │  ├─ Transition: PROCESSING → RETRYING                     │
│     │  ├─ Update context (attempt, last_error, next_retry)      │
│     │  └─ nack() → Redis redelivery                             │
│     └─ On Exhausted (retry >= max):                             │
│        ├─ Transition: RETRYING → EXHAUSTED                      │
│        ├─ Update context (exhausted_at, final_error)            │
│        ├─ Publish → dlq-subject                                 │
│        └─ ack() (no redelivery)                                 │
└─────────────────────────────────────────────────────────────────┘
                         │
           ┌─────────────┴─────────────┐
           ▼                           ▼
┌────────────────────────┐   ┌────────────────────────┐
│ result-event-subject   │   │    dlq-subject         │
│ (Success events)       │   │ (Exhausted events)     │
└────────────────────────┘   └────────────────────────┘
```

---

## 📊 Estado Transitions

### Estados Involucrados (Subset de EventState)

| Estado           | Descripción                              | Transiciones Válidas    |
| ---------------- | ---------------------------------------- | ----------------------- |
| `PENDING`        | Encolado, esperando procesamiento        | → PROCESSING            |
| `PROCESSING`     | En procesamiento activo                  | → COMPLETED, RETRYING   |
| `RETRYING`       | Falló, reintentando (attempt < max)      | → PROCESSING, EXHAUSTED |
| `TEMPORAL_ERROR` | Error temporal detectado (puede retryar) | → RETRYING              |
| `COMPLETED`      | Procesado exitosamente                   | (final)                 |
| `EXHAUSTED`      | Agotó reintentos (attempt >= max)        | (final)                 |
| `FAILED`         | Error permanente (sin retry posible)     | (final)                 |

### Diagrama de Transiciones

```
                  PENDING
                     │
                     ▼
              PROCESSING ──┐ Success
                     │     └────────→ COMPLETED (✅ Final)
                     │ Transient Error
                     ▼
             TEMPORAL_ERROR
                     │
                     ▼
                 RETRYING ──┐ Retry Exhausted
                     │      └────────→ EXHAUSTED (❌ Final → DLQ)
                     │ Retry Available
                     └──────────────→ PROCESSING (loop)
```

### Transition Rules

```python
VALID_TRANSITIONS = {
    EventState.PENDING: [EventState.PROCESSING],
    EventState.PROCESSING: [
        EventState.COMPLETED,      # Success
        EventState.TEMPORAL_ERROR, # Transient error detected
        EventState.FAILED,         # Permanent error
    ],
    EventState.TEMPORAL_ERROR: [EventState.RETRYING],
    EventState.RETRYING: [
        EventState.PROCESSING,     # Retry attempt
        EventState.EXHAUSTED,      # Max retries exceeded
    ],
    # Final states (no transitions)
    EventState.COMPLETED: [],
    EventState.EXHAUSTED: [],
    EventState.FAILED: [],
}
```

---

## 🔧 Event.context Structure (TypedDict)

### EventProcessingContext (TypedDict)

```python
from typing import TypedDict, NotRequired
from datetime import datetime

class RetryMetadata(TypedDict):
    """Metadata de reintentos"""
    current_attempt: int              # Current retry attempt (0-based)
    max_attempts: int                 # Max allowed attempts
    last_error: NotRequired[str]      # Last error message
    last_retry_at: NotRequired[str]   # ISO 8601 timestamp
    next_retry_at: NotRequired[str]   # ISO 8601 timestamp (backoff calculation)
    backoff_seconds: NotRequired[float]  # Calculated backoff for next retry

class ProcessingMetadata(TypedDict):
    """Metadata de procesamiento"""
    started_at: str                   # ISO 8601 timestamp
    completed_at: NotRequired[str]    # ISO 8601 timestamp (if success)
    duration_ms: NotRequired[int]     # Processing duration in milliseconds
    worker_id: NotRequired[str]       # Identifier of processing worker

class ExhaustedMetadata(TypedDict):
    """Metadata cuando se agotaron reintentos"""
    exhausted_at: str                 # ISO 8601 timestamp
    final_error: str                  # Final error before giving up
    total_attempts: int               # Total attempts made
    dlq_published_at: NotRequired[str]  # When moved to DLQ

class EventProcessingContext(TypedDict):
    """
    Structure for Event.context field.
    Tracks processing lifecycle metadata.
    """
    retry: NotRequired[RetryMetadata]
    processing: NotRequired[ProcessingMetadata]
    exhausted: NotRequired[ExhaustedMetadata]
    custom: NotRequired[dict[str, Any]]  # User-defined metadata
```

### Ejemplo de Event.context en Diferentes Estados

**Estado: PENDING** (recién encolado)

```json
{
  "retry": {
    "current_attempt": 0,
    "max_attempts": 5
  }
}
```

**Estado: RETRYING** (después de 1er error)

```json
{
  "retry": {
    "current_attempt": 1,
    "max_attempts": 5,
    "last_error": "ConnectionError: Redis timeout",
    "last_retry_at": "2026-01-03T10:15:30Z",
    "next_retry_at": "2026-01-03T10:16:00Z",
    "backoff_seconds": 30.0
  },
  "processing": {
    "started_at": "2026-01-03T10:15:00Z"
  }
}
```

**Estado: EXHAUSTED** (después de max retries)

```json
{
  "retry": {
    "current_attempt": 5,
    "max_attempts": 5,
    "last_error": "ConnectionError: Redis permanently unavailable"
  },
  "processing": {
    "started_at": "2026-01-03T10:15:00Z"
  },
  "exhausted": {
    "exhausted_at": "2026-01-03T10:20:00Z",
    "final_error": "ConnectionError: Redis permanently unavailable",
    "total_attempts": 5,
    "dlq_published_at": "2026-01-03T10:20:01Z"
  }
}
```

**Estado: COMPLETED** (éxito)

```json
{
  "retry": {
    "current_attempt": 2,
    "max_attempts": 5
  },
  "processing": {
    "started_at": "2026-01-03T10:15:00Z",
    "completed_at": "2026-01-03T10:16:45Z",
    "duration_ms": 105000,
    "worker_id": "worker-01"
  }
}
```

---

## 🔄 Retry Strategy Configuration

### Configuración de Tenacity

```python
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    after_log,
)

# Retry configuration for handle_processing_event_queue
PROCESSING_RETRY_CONFIG = {
    "stop": stop_after_attempt(5),  # Max 5 attempts
    "wait": wait_exponential(
        multiplier=2,   # 2s, 4s, 8s, 16s, 32s
        min=2,          # Min 2s
        max=60,         # Max 60s
    ),
    "retry": retry_if_exception_type((
        ConnectionError,      # Network errors
        TimeoutError,         # Timeout errors
        # Add other transient exceptions
    )),
    "before_sleep": before_sleep_log(logger, logging.WARNING),
    "after": after_log(logger, logging.INFO),
    "reraise": True,
}
```

### Timeline de Reintentos

```
Attempt 1: Immediate (t=0s)
Attempt 2: After 2s  (t=2s)
Attempt 3: After 4s  (t=6s)
Attempt 4: After 8s  (t=14s)
Attempt 5: After 16s (t=30s)
───────────────────────────────
Total:     ~30s before exhausted
```

---

## 💻 Implementación Propuesta

### 1. UseCase: ProcessEventUseCase

```python
# app/core/usecases/event_usecases.py

from datetime import datetime, timezone
from typing import Any

class ProcessEventUseCaseInput(BaseModel):
    event_id: UUID
    payload: dict[str, Any]

class ProcessEventUseCaseOutput(BaseModel):
    event_id: UUID
    state: EventState
    result: dict[str, Any] | None

class ProcessEventUseCase(AsyncUseCase[ProcessEventUseCaseInput, ProcessEventUseCaseOutput]):
    """
    Process an event (business logic).

    Transitions:
    - PENDING → PROCESSING (start)
    - PROCESSING → COMPLETED (success)
    - PROCESSING → TEMPORAL_ERROR (transient error)
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

        # 2. Validate state (must be PENDING or RETRYING)
        if event.state not in [EventState.PENDING, EventState.RETRYING]:
            return Err(ErrorDetail(
                code="INVALID_STATE",
                message=f"Event {event.id} is in state {event.state}, expected PENDING or RETRYING"
            ))

        # 3. Transition to PROCESSING
        event.state = EventState.PROCESSING
        event.context = event.context or {}
        event.context["processing"] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        transition = EventTransition(
            from_state=EventState.PENDING if event.state == EventState.PENDING else EventState.RETRYING,
            to_state=EventState.PROCESSING,
            event_id=event.id,
        )
        event.transitions.append(transition)

        # 4. Execute business logic (simulated for MVP)
        try:
            # TODO: Replace with actual business logic
            result = await self._simulate_processing(input.payload)

            # 5. Success: Transition to COMPLETED
            event.state = EventState.COMPLETED
            event.result = result
            event.context["processing"]["completed_at"] = datetime.now(timezone.utc).isoformat()
            event.context["processing"]["duration_ms"] = int(
                (datetime.now(timezone.utc) - datetime.fromisoformat(event.context["processing"]["started_at"])).total_seconds() * 1000
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
                result=result,
            ))

        except (ConnectionError, TimeoutError) as e:
            # Transient error: mark for retry
            event.state = EventState.TEMPORAL_ERROR
            event.context["retry"] = event.context.get("retry", {
                "current_attempt": 0,
                "max_attempts": 5,
            })
            event.context["retry"]["last_error"] = str(e)
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

    async def _simulate_processing(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Simulate business logic processing.
        Replace with actual implementation.
        """
        # Simulate 100ms processing time
        await asyncio.sleep(0.1)

        # Simulate random failure (10% chance)
        if random.random() < 0.1:
            raise ConnectionError("Simulated transient error")

        return {
            "payload": payload,
            "type": "processed",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
```

### 2. UseCase: ExhaustEventUseCase

```python
# app/core/usecases/event_usecases.py

class ExhaustEventUseCaseInput(BaseModel):
    event_id: UUID
    final_error: str

class ExhaustEventUseCaseOutput(BaseModel):
    event_id: UUID
    state: EventState
    exhausted_at: str

class ExhaustEventUseCase(AsyncUseCase[ExhaustEventUseCaseInput, ExhaustEventUseCaseOutput]):
    """
    Mark event as EXHAUSTED after max retries.

    Transitions:
    - RETRYING → EXHAUSTED
    """

    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def execute(
        self, input: ExhaustEventUseCaseInput
    ) -> Result[ExhaustEventUseCaseOutput, ErrorDetail]:
        # 1. Load event
        event_result = await self.uow.events.get_by_id(input.event_id)
        if event_result.is_err():
            return event_result

        event = event_result.unwrap()

        # 2. Validate state (must be RETRYING or TEMPORAL_ERROR)
        if event.state not in [EventState.RETRYING, EventState.TEMPORAL_ERROR]:
            return Err(ErrorDetail(
                code="INVALID_STATE",
                message=f"Event {event.id} is in state {event.state}, expected RETRYING or TEMPORAL_ERROR"
            ))

        # 3. Transition to EXHAUSTED
        exhausted_at = datetime.now(timezone.utc).isoformat()

        event.state = EventState.EXHAUSTED
        event.context = event.context or {}
        event.context["exhausted"] = {
            "exhausted_at": exhausted_at,
            "final_error": input.final_error,
            "total_attempts": event.context.get("retry", {}).get("current_attempt", 0),
        }

        transition = EventTransition(
            from_state=EventState.RETRYING,
            to_state=EventState.EXHAUSTED,
            event_id=event.id,
        )
        event.transitions.append(transition)

        # 4. Save
        save_result = await self.uow.events.save(event)
        if save_result.is_err():
            return save_result

        return Ok(ExhaustEventUseCaseOutput(
            event_id=event.id,
            state=event.state,
            exhausted_at=exhausted_at,
        ))
```

### 3. Handler: handle_processing_event_queue (Refactored)

```python
# app/infrastructure/redis/main.py

@ProcessingEventSubscriber
@broker.publisher(stream="result-event-subject")
async def handle_processing_event_queue(
    body: EnqueuedEventUseCaseOutput,  # From enqueue handler
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any] | None:
    """
    Process events from processing-event-subject stream.

    Implements retry strategy with exponential backoff:
    - Max 5 attempts with 2s, 4s, 8s, 16s, 32s delays

    Flow:
    1. PENDING → PROCESSING (start processing)
    2. On Success: PROCESSING → COMPLETED + publish to result-event-subject
    3. On Transient Error: PROCESSING → RETRYING + nack (Redis redelivery)
    4. On Exhausted: RETRYING → EXHAUSTED + publish to dlq-subject

    See: docs/MVP_DESIGN_PROCESSING_HANDLER.md
    """
    event_id = body.id

    try:
        logger.info(f"Processing event {event_id}")

        # Initialize retry metadata in event.context
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            # Load event to check current attempt
            event_result = await uow.events.get_by_id(event_id)
            if event_result.is_err():
                logger.error(f"Event {event_id} not found in DB")
                await msg.nack()
                return None

            event = event_result.unwrap()
            context = event.context or {}
            retry_meta = context.get("retry", {
                "current_attempt": 0,
                "max_attempts": 5,
            })
            current_attempt = retry_meta.get("current_attempt", 0)
            max_attempts = retry_meta.get("max_attempts", 5)

            # Check if exhausted
            if current_attempt >= max_attempts:
                logger.warning(f"Event {event_id} exhausted (attempt {current_attempt}/{max_attempts})")

                # Transition to EXHAUSTED
                exhaust_usecase = ExhaustEventUseCase(uow)
                exhaust_result = await exhaust_usecase.execute(
                    ExhaustEventUseCaseInput(
                        event_id=event_id,
                        final_error=retry_meta.get("last_error", "Max retries exceeded"),
                    )
                )

                if exhaust_result.is_err():
                    logger.error(f"Failed to exhaust event {event_id}: {exhaust_result.unwrap_err()}")
                    await msg.nack()
                    return None

                # Publish to DLQ
                await broker.publish(
                    exhaust_result.unwrap(),
                    stream="dlq-subject",
                )
                logger.info(f"Event {event_id} moved to DLQ")

                # Update context with DLQ publish timestamp
                event.context["exhausted"]["dlq_published_at"] = datetime.now(timezone.utc).isoformat()
                await uow.events.save(event)

                await msg.ack()  # Don't reprocess
                return None

        # Process event (with retry strategy)
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5 - current_attempt),  # Remaining attempts
            wait=wait_exponential(multiplier=2, min=2, max=60),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        ):
            with attempt:
                async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
                    # Execute processing
                    process_usecase = ProcessEventUseCase(uow)
                    process_result = await process_usecase.execute(
                        ProcessEventUseCaseInput(
                            event_id=event_id,
                            payload=body.model_dump(),
                        )
                    )

                    if process_result.is_err():
                        logger.error(f"Processing failed for event {event_id}: {process_result.unwrap_err()}")
                        await msg.nack()
                        return None

                    output = process_result.unwrap()
                    logger.info(f"Event {event_id} processed successfully: {output.state}")

                    # Success: publish to result stream
                    await msg.ack()
                    return output.model_dump()

    except RetryError as retry_err:
        # All retries exhausted at handler level
        logger.error(f"Processing exhausted for event {event_id}: {retry_err.last_attempt.exception()}")

        # Increment attempt counter and transition to RETRYING
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            event_result = await uow.events.get_by_id(event_id)
            if event_result.is_ok():
                event = event_result.unwrap()
                context = event.context or {}
                retry_meta = context.get("retry", {
                    "current_attempt": 0,
                    "max_attempts": 5,
                })
                retry_meta["current_attempt"] += 1
                retry_meta["last_error"] = str(retry_err.last_attempt.exception())
                retry_meta["last_retry_at"] = datetime.now(timezone.utc).isoformat()

                context["retry"] = retry_meta
                event.context = context

                # Transition to RETRYING
                if event.state == EventState.TEMPORAL_ERROR:
                    event.state = EventState.RETRYING
                    transition = EventTransition(
                        from_state=EventState.TEMPORAL_ERROR,
                        to_state=EventState.RETRYING,
                        event_id=event.id,
                    )
                    event.transitions.append(transition)

                await uow.events.save(event)

        # nack → Redis will redeliver
        await msg.nack()
        return None

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error processing event {event_id}: {e}", exc_info=True)
        await msg.nack()
        return None
```

---

## 🧪 Testing Strategy

### Test Structure

```
tests/
├── unit/
│   ├── test_process_event_usecase_unit.py      # ProcessEventUseCase logic
│   ├── test_exhaust_event_usecase_unit.py      # ExhaustEventUseCase logic
│   ├── test_event_context_structure_unit.py    # TypedDict validation
│   └── test_state_transitions_unit.py          # VALID_TRANSITIONS rules
│
└── functional/
    ├── test_processing_handler_happy_path.py   # End-to-end success flow
    ├── test_processing_handler_retry.py        # Retry scenarios
    ├── test_processing_handler_exhausted.py    # Exhausted → DLQ flow
    └── test_processing_handler_concurrency.py  # Race conditions
```

### Unit Tests (ProcessEventUseCase)

```python
# tests/unit/test_process_event_usecase_unit.py

@pytest.mark.asyncio
async def test_u1_pending_to_completed_success(uow_mock):
    """Test successful processing: PENDING → PROCESSING → COMPLETED"""
    event = Event(
        id=uuid4(),
        name="Test Event",
        state=EventState.PENDING,
        payload={"data": "test"},
        context={},
    )
    uow_mock.events.get_by_id = AsyncMock(return_value=Ok(event))
    uow_mock.events.save = AsyncMock(return_value=Ok(event))

    usecase = ProcessEventUseCase(uow=uow_mock)
    result = await usecase.execute(ProcessEventUseCaseInput(
        event_id=event.id,
        payload={"data": "test"},
    ))

    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.COMPLETED
    assert output.result is not None

    # Verify transitions
    assert len(event.transitions) == 2
    assert event.transitions[0].to_state == EventState.PROCESSING
    assert event.transitions[1].to_state == EventState.COMPLETED

    # Verify context
    assert "processing" in event.context
    assert "started_at" in event.context["processing"]
    assert "completed_at" in event.context["processing"]


@pytest.mark.asyncio
async def test_u2_processing_transient_error(uow_mock):
    """Test transient error: PROCESSING → TEMPORAL_ERROR"""
    event = Event(
        id=uuid4(),
        name="Test Event",
        state=EventState.PENDING,
        payload={"data": "test"},
        context={},
    )
    uow_mock.events.get_by_id = AsyncMock(return_value=Ok(event))
    uow_mock.events.save = AsyncMock(return_value=Ok(event))

    usecase = ProcessEventUseCase(uow=uow_mock)

    # Mock _simulate_processing to raise transient error
    with patch.object(usecase, "_simulate_processing", side_effect=ConnectionError("Redis timeout")):
        with pytest.raises(ConnectionError):
            await usecase.execute(ProcessEventUseCaseInput(
                event_id=event.id,
                payload={"data": "test"},
            ))

    # Verify state transition
    assert event.state == EventState.TEMPORAL_ERROR
    assert "retry" in event.context
    assert event.context["retry"]["last_error"] == "Redis timeout"


@pytest.mark.asyncio
async def test_u3_invalid_state_rejection(uow_mock):
    """Test that processing rejects events not in PENDING/RETRYING"""
    event = Event(
        id=uuid4(),
        name="Test Event",
        state=EventState.COMPLETED,  # Invalid state
        payload={"data": "test"},
        context={},
    )
    uow_mock.events.get_by_id = AsyncMock(return_value=Ok(event))

    usecase = ProcessEventUseCase(uow=uow_mock)
    result = await usecase.execute(ProcessEventUseCaseInput(
        event_id=event.id,
        payload={"data": "test"},
    ))

    assert result.is_err()
    error = result.unwrap_err()
    assert error.code == "INVALID_STATE"
```

### Unit Tests (ExhaustEventUseCase)

```python
# tests/unit/test_exhaust_event_usecase_unit.py

@pytest.mark.asyncio
async def test_u1_exhaust_retrying_event(uow_mock):
    """Test exhausting event: RETRYING → EXHAUSTED"""
    event = Event(
        id=uuid4(),
        name="Test Event",
        state=EventState.RETRYING,
        context={
            "retry": {
                "current_attempt": 5,
                "max_attempts": 5,
                "last_error": "ConnectionError: Timeout",
            }
        },
    )
    uow_mock.events.get_by_id = AsyncMock(return_value=Ok(event))
    uow_mock.events.save = AsyncMock(return_value=Ok(event))

    usecase = ExhaustEventUseCase(uow=uow_mock)
    result = await usecase.execute(ExhaustEventUseCaseInput(
        event_id=event.id,
        final_error="Max retries exceeded",
    ))

    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.EXHAUSTED

    # Verify exhausted metadata
    assert "exhausted" in event.context
    assert event.context["exhausted"]["total_attempts"] == 5
    assert event.context["exhausted"]["final_error"] == "Max retries exceeded"

    # Verify transition
    assert len(event.transitions) == 1
    assert event.transitions[0].to_state == EventState.EXHAUSTED
```

### Functional Tests (Happy Path)

```python
# tests/functional/test_processing_handler_happy_path.py

@pytest.mark.asyncio
async def test_f1_end_to_end_success(uow_factory, dbsession):
    """Test complete flow: PENDING → PROCESSING → COMPLETED"""
    # Setup: Create event in PENDING state
    event = Event(
        name="Test Event",
        state=EventState.PENDING,
        payload={"data": "test"},
        context={
            "retry": {
                "current_attempt": 0,
                "max_attempts": 5,
            }
        },
    )
    dbsession.add(event)
    await dbsession.commit()
    await dbsession.refresh(event)

    # Execute: Process event
    async with uow_factory() as uow:
        usecase = ProcessEventUseCase(uow)
        result = await usecase.execute(ProcessEventUseCaseInput(
            event_id=event.id,
            payload=event.payload,
        ))

    # Verify: Event completed
    assert result.is_ok()
    output = result.unwrap()
    assert output.state == EventState.COMPLETED

    # Verify DB state
    await dbsession.refresh(event)
    assert event.state == EventState.COMPLETED
    assert "processing" in event.context
    assert "completed_at" in event.context["processing"]

    # Verify transitions in DB
    transitions = await dbsession.execute(
        select(EventTransition).where(EventTransition.event_id == event.id)
    )
    transition_list = transitions.scalars().all()
    assert len(transition_list) == 2
    assert transition_list[0].to_state == EventState.PROCESSING
    assert transition_list[1].to_state == EventState.COMPLETED
```

### Functional Tests (Retry Scenarios)

```python
# tests/functional/test_processing_handler_retry.py

@pytest.mark.asyncio
async def test_f1_retry_after_transient_error(uow_factory, dbsession):
    """Test retry flow: PENDING → PROCESSING → RETRYING → PROCESSING → COMPLETED"""
    event = Event(
        name="Test Event",
        state=EventState.PENDING,
        payload={"data": "test"},
        context={
            "retry": {
                "current_attempt": 0,
                "max_attempts": 5,
            }
        },
    )
    dbsession.add(event)
    await dbsession.commit()
    await dbsession.refresh(event)

    # First attempt: Fail with transient error
    async with uow_factory() as uow:
        usecase = ProcessEventUseCase(uow)
        with patch.object(usecase, "_simulate_processing", side_effect=ConnectionError("Redis timeout")):
            with pytest.raises(ConnectionError):
                await usecase.execute(ProcessEventUseCaseInput(
                    event_id=event.id,
                    payload=event.payload,
                ))

    # Verify: Event in TEMPORAL_ERROR
    await dbsession.refresh(event)
    assert event.state == EventState.TEMPORAL_ERROR
    assert event.context["retry"]["last_error"] == "Redis timeout"

    # Simulate handler incrementing attempt and transitioning to RETRYING
    event.state = EventState.RETRYING
    event.context["retry"]["current_attempt"] = 1
    transition = EventTransition(
        from_state=EventState.TEMPORAL_ERROR,
        to_state=EventState.RETRYING,
        event_id=event.id,
    )
    event.transitions.append(transition)
    await dbsession.commit()

    # Second attempt: Success
    async with uow_factory() as uow:
        usecase = ProcessEventUseCase(uow)
        result = await usecase.execute(ProcessEventUseCaseInput(
            event_id=event.id,
            payload=event.payload,
        ))

    # Verify: Event completed
    assert result.is_ok()
    await dbsession.refresh(event)
    assert event.state == EventState.COMPLETED
    assert event.context["retry"]["current_attempt"] == 1  # Successfully retried


@pytest.mark.asyncio
async def test_f2_exhaust_after_max_retries(uow_factory, dbsession):
    """Test exhaustion: RETRYING (x5) → EXHAUSTED"""
    event = Event(
        name="Test Event",
        state=EventState.RETRYING,
        payload={"data": "test"},
        context={
            "retry": {
                "current_attempt": 5,  # Already at max
                "max_attempts": 5,
                "last_error": "ConnectionError: Persistent failure",
            }
        },
    )
    dbsession.add(event)
    await dbsession.commit()
    await dbsession.refresh(event)

    # Execute: Exhaust event
    async with uow_factory() as uow:
        usecase = ExhaustEventUseCase(uow)
        result = await usecase.execute(ExhaustEventUseCaseInput(
            event_id=event.id,
            final_error="Max retries exceeded",
        ))

    # Verify: Event exhausted
    assert result.is_ok()
    await dbsession.refresh(event)
    assert event.state == EventState.EXHAUSTED
    assert "exhausted" in event.context
    assert event.context["exhausted"]["total_attempts"] == 5
```

### Functional Tests (Concurrency)

```python
# tests/functional/test_processing_handler_concurrency.py

@pytest.mark.asyncio
async def test_c1_concurrent_processing_same_event(uow_factory, dbsession):
    """Test that concurrent processing of same event is handled safely"""
    event = Event(
        name="Test Event",
        state=EventState.PENDING,
        payload={"data": "test"},
        context={
            "retry": {
                "current_attempt": 0,
                "max_attempts": 5,
            }
        },
    )
    dbsession.add(event)
    await dbsession.commit()
    await dbsession.refresh(event)

    # Simulate 2 workers processing simultaneously
    async def process_worker():
        async with uow_factory() as uow:
            usecase = ProcessEventUseCase(uow)
            try:
                result = await usecase.execute(ProcessEventUseCaseInput(
                    event_id=event.id,
                    payload=event.payload,
                ))
                return result
            except Exception as e:
                return Err(ErrorDetail(code="ERROR", message=str(e)))

    # Execute concurrently
    results = await asyncio.gather(
        process_worker(),
        process_worker(),
        return_exceptions=True,
    )

    # Verify: Only one should succeed (or both handle gracefully)
    success_count = sum(1 for r in results if isinstance(r, Ok))
    assert success_count >= 1  # At least one succeeded

    # Verify final state
    await dbsession.refresh(event)
    assert event.state in [EventState.COMPLETED, EventState.PROCESSING]
```

---

## 📊 Métricas de Éxito

| Métrica                | Target        | Validación                            |
| ---------------------- | ------------- | ------------------------------------- |
| **Tests Passing**      | 100%          | All unit + functional tests pass      |
| **Coverage**           | ≥85%          | For new ProcessEventUseCase + handler |
| **State Transitions**  | Todas válidas | VALID_TRANSITIONS enforced            |
| **Retry Success Rate** | >80%          | Events completed after retry          |
| **Exhausted Rate**     | <10%          | Events moved to DLQ                   |
| **Type Safety**        | 0 mypy errors | TypedDict validated                   |

---

## 📚 Documentación a Actualizar

### Agents.md (Sección Nueva)

```markdown
### 🔄 Event Processing Pattern (Mejora #5)

**Scenario**: Procesar eventos con retry strategy + DLQ

**States**: PENDING → PROCESSING → RETRYING → EXHAUSTED/COMPLETED

**Key Components**:

- ProcessEventUseCase: Business logic con retry handling
- ExhaustEventUseCase: Move to DLQ after max retries
- handle_processing_event_queue: Handler con tenacity retry

**Retry Configuration**:

- Max attempts: 5
- Backoff: 2s, 4s, 8s, 16s, 32s (exponential)
- Total timeout: ~30s before exhausted

**Testing**:

- Unit: State transitions, retry logic, context updates
- Functional: End-to-end flows, concurrency, DLQ publishing
```

### RETRY_STRATEGY.md (Actualizar)

Agregar sección para `handle_processing_event_queue`:

```markdown
## Processing Queue Retry Configuration

**Operation**: handle_processing_event_queue
**Max Attempts**: 5
**Backoff**: Exponential (2s, 4s, 8s, 16s, 32s)
**Total Timeout**: ~30s

### Timeline

Attempt 1: t=0s
Attempt 2: t=2s
Attempt 3: t=6s
Attempt 4: t=14s
Attempt 5: t=30s
───────────────
After exhaustion → DLQ
```

---

## 🎯 Orden de Implementación

### Fase 1: Core Components (1 día)

1. ✅ Define TypedDict structures (EventProcessingContext)
2. ✅ Implement ProcessEventUseCase
3. ✅ Implement ExhaustEventUseCase
4. ✅ Unit tests for use cases

### Fase 2: Handler Implementation (1 día)

1. ✅ Refactor handle_processing_event_queue
2. ✅ Add retry logic with tenacity
3. ✅ Integrate ProcessEventUseCase
4. ✅ Integrate ExhaustEventUseCase
5. ✅ Add DLQ publishing

### Fase 3: Testing (0.5 días)

1. ✅ Functional tests (happy path)
2. ✅ Functional tests (retry scenarios)
3. ✅ Functional tests (exhausted → DLQ)
4. ✅ Concurrency tests

### Fase 4: Documentation (0.5 días)

1. ✅ Update Agents.md
2. ✅ Update RETRY_STRATEGY.md
3. ✅ Create examples in docs/

**Total Estimado**: 3 días

---

## ❓ Preguntas para Resolver

1. **Simulación de Business Logic**: ¿Qué lógica real debe ejecutarse en `_simulate_processing`?

   - Opciones: Scraping, API calls, transformaciones?

2. **DLQ Consumer**: ¿Se requiere un consumer para `dlq-subject` en este MVP?

   - O solo logging por ahora?

3. **Retry Backoff**: ¿La configuración 2s-32s es apropiada para tu caso de uso?

   - ¿Necesitas ajustarla?

4. **Permanent Errors**: ¿Qué errores NO deben retryarse (permanent failures)?

   - Ejemplo: ValidationError → Directamente FAILED?

5. **Context Migrations**: ¿Eventos existentes sin `context` necesitan migración?
   - O se asume que solo eventos nuevos tendrán context?

---

## ✅ Checklist para Aprobación

- [ ] Revisar estructura de estados (PROCESSING → RETRYING → EXHAUSTED)
- [ ] Aprobar TypedDict para Event.context
- [ ] Validar retry configuration (5x, exponential backoff)
- [ ] Aprobar testing strategy (unit + functional)
- [ ] Confirmar orden de implementación (3 días estimados)
- [ ] Resolver preguntas pendientes

---

**Próximo Paso**: Revisión y aprobación del diseño antes de implementación

**Documentación Relacionada**:

- [RETRY_STRATEGY.md](RETRY_STRATEGY.md)
- [TRANSACTION_PATTERN.md](TRANSACTION_PATTERN.md)
- [PEER_REVIEW_PENDING.md](PEER_REVIEW_PENDING.md)
