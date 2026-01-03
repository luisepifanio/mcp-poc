# 🔄 Retry Strategy Documentation

**Date**: January 3, 2026  
**Status**: ✅ Implemented  
**Library**: tenacity 9.1.2

---

## 📋 Overview

Implementación de estrategia de reintentos con backoff exponencial para operaciones críticas en el event processing pipeline.

### Operaciones con Retry

| Operación   | Max Attempts | Base Delay | Max Delay | Total Time | Comportamiento              |
| ----------- | ------------ | ---------- | --------- | ---------- | --------------------------- |
| **Enqueue** | 3            | 1s         | 10s       | ~7s        | Save evento a DB            |
| **Publish** | 5            | 0.5s       | 10s       | ~15.5s     | Publish a processing stream |

---

## 🎯 Objetivos

1. **Resiliencia**: Manejar fallos temporales (network, DB locks, etc.)
2. **Atomicidad**: Si publish falla after all retries → rollback DB save
3. **Visibilidad**: Logs estructurados de cada intento
4. **Backoff Exponencial**: Evitar sobrecargar recursos fallando

---

## 🔧 Implementación

### Retry para Enqueue Operation

```python
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    after_log,
)

# Max 3 attempts: 1s, 2s, 4s (total ~7s)
async for attempt in AsyncRetrying(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO),
    reraise=True,
):
    with attempt:
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            usecase = EnqueueEventUseCase(uow)
            result = await usecase.execute(event)
            # ...
```

**Timeline**:

- Attempt 1: Immediate
- Attempt 2: After 1s (if failed)
- Attempt 3: After 2s more (total 3s from start)
- Total: ~7s before giving up

**Errores retryables**:

- Database connection errors
- Transaction deadlocks
- Temporary network issues

### Retry para Publish Operation

```python
# Max 5 attempts: 0.5s, 1s, 2s, 4s, 8s (total ~15.5s)
try:
    async for publish_attempt in AsyncRetrying(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO),
        reraise=True,
    ):
        with publish_attempt:
            await broker.publish(
                {
                    "event_id": str(value.id),
                    "name": value.name,
                    # ...
                },
                stream="processing-event-subject",
            )
except RetryError as retry_err:
    # If publish fails after all retries, rollback TX
    logger.error(f"Publish failed after all retries: {retry_err.last_attempt.exception()}")
    raise  # Will trigger TX rollback
```

**Timeline**:

- Attempt 1: Immediate
- Attempt 2: After 0.5s (if failed)
- Attempt 3: After 1s more (total 1.5s)
- Attempt 4: After 2s more (total 3.5s)
- Attempt 5: After 4s more (total 7.5s)
- Total: ~15.5s before giving up

**Errores retryables**:

- Redis connection errors
- Network timeouts
- Broker temporary unavailability

---

## 📊 Logging & Observability

### Log Structure

Cada retry genera logs estructurados:

```python
# Before retry
WARNING: Retrying app.infrastructure.redis.main.handle_enqueue_event in 1.0 seconds as it raised <Exception>

# After attempt
INFO: Finished call to app.infrastructure.redis.main.handle_enqueue_event after 0.005s
```

### Métricas a Monitorear

| Métrica                | Descripción                                 | Threshold |
| ---------------------- | ------------------------------------------- | --------- |
| **retry_count**        | # de reintentos por operación               | < 2 avg   |
| **retry_success_rate** | % de operaciones exitosas after retry       | > 95%     |
| **max_retry_failures** | # de operaciones fallidas after all retries | < 1%      |
| **retry_latency**      | Tiempo total incluyendo retries             | < 25s p99 |

---

## 🎯 Casos de Uso

### Caso 1: Temporary DB Lock

```
Timeline:
T0:   Attempt 1 → DB lock (fail)
T1:   Attempt 2 → DB lock released (success)

Result: ✅ Enqueued after 1s
```

### Caso 2: Redis Connection Lost

```
Timeline:
T0:   Save event → success
      Publish → Redis down (fail)
T0.5: Publish → Redis still down (fail)
T1.5: Publish → Redis recovered (success)

Result: ✅ Published after 3 retries (~3.5s)
```

### Caso 3: All Retries Exhausted

```
Timeline:
T0:   Enqueue attempt 1 → DB down (fail)
T1:   Enqueue attempt 2 → DB down (fail)
T3:   Enqueue attempt 3 → DB down (fail)

Result: ❌ RetryError raised
Action: msg.nack() → Redis redelivers message
```

---

## 🔍 Transaction Atomicity

### Guarantee: Save + Publish = 1 Unit

```python
async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
    # Step 1: Save (with retry)
    result = await usecase.execute(event)

    if result.is_ok():
        try:
            # Step 2: Publish (with retry)
            await broker.publish({...})
        except RetryError:
            # Publish failed after all retries
            raise  # → Triggers rollback

    # Success: Both save + publish succeeded
    # __aexit__ commits transaction
```

**Atomicity Preserved**:

- ✅ If save fails → No DB record, no publish
- ✅ If publish fails → TX rollback, no DB record
- ✅ If both succeed → Single atomic commit

---

## 🚨 Error Handling Flowchart

```
Event Received
    │
    ▼
Enqueue (Retry: 3x, 1s backoff)
    │
    ├─ Success? ──→ YES ─┐
    │                    │
    └─ NO (after 3x) ────┼─→ nack() → Redis redelivery
                         │
                         ▼
            Publish (Retry: 5x, 0.5s backoff)
                         │
                ├─ Success? ──→ YES ─→ Commit TX + ack()
                │
                └─ NO (after 5x) ────→ Rollback TX + nack()
```

---

## 📚 Configuration

### Default Values (Production)

```python
ENQUEUE_MAX_ATTEMPTS = 3
ENQUEUE_BACKOFF_MULTIPLIER = 1  # 1s base
ENQUEUE_BACKOFF_MAX = 10  # 10s max

PUBLISH_MAX_ATTEMPTS = 5
PUBLISH_BACKOFF_MULTIPLIER = 0.5  # 0.5s base
PUBLISH_BACKOFF_MAX = 10  # 10s max
```

### Adjusting for Different Environments

```python
# Development: Faster failures
ENQUEUE_MAX_ATTEMPTS = 2
ENQUEUE_BACKOFF_MULTIPLIER = 0.5

# Production: More resilient
ENQUEUE_MAX_ATTEMPTS = 5
ENQUEUE_BACKOFF_MULTIPLIER = 2
```

---

## 🧪 Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_enqueue_retry_on_db_lock():
    """Test that enqueue retries on DB lock errors"""
    uow_mock = MagicMock()
    uow_mock.events.save_or_resolve_one = AsyncMock(
        side_effect=[
            Exception("DB lock"),  # Attempt 1: fail
            Exception("DB lock"),  # Attempt 2: fail
            Ok(event),             # Attempt 3: success
        ]
    )

    # Should succeed on 3rd attempt
    result = await handle_enqueue_event(...)
    assert result.is_ok()
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_publish_rollback_on_all_failures():
    """Test that TX rollback when publish fails after all retries"""
    # Setup: Event saves successfully
    # Setup: Redis broker always fails

    result = await handle_enqueue_event(...)

    # Verify: Event NOT in DB (rollback occurred)
    assert db_event is None
```

---

## 🔗 Related Documentation

- [TRANSACTION_PATTERN.md](TRANSACTION_PATTERN.md) - Handler-managed transaction orchestration
- [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) - Phase 1-5 implementation summary
- [Agents.md](../Agents.md) - Development workflow with patterns

---

## 📋 Maintenance Checklist

- [ ] Monitor retry metrics in production
- [ ] Adjust backoff parameters based on observed latency
- [ ] Add custom retry predicates for specific error types
- [ ] Implement circuit breaker if retry rate > 10%
- [ ] Document new retryable error types as discovered

---

**Last Updated**: January 3, 2026  
**Next Review**: After observing production metrics (1 week)
