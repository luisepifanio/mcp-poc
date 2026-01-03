# 🔄 Background Event Reprocessing - Backlog Requirement

**Date**: January 3, 2026  
**Status**: 📋 Backlog (Not Implemented)  
**Priority**: HIGH  
**Estimated Effort**: 3-5 days

---

## 📋 Requerimiento

**Usuario**: "Deberemos evaluar una manera de reprocesar asincronamente / recuperar aquellos eventos en estados CREATED/PENDING que no hayan podido ser procesados por algun motivo"

### Problema a Resolver

Eventos pueden quedar "atascados" en estados `CREATED` o `PENDING` por varios motivos:

1. **Sistema caído durante procesamiento**

   - App crashea después de crear evento pero antes de publicar
   - Redis down durante publish (mensaje nack'd pero no reintentado)

2. **Failures after max retries**

   - Retry strategy agota intentos (3x enqueue, 5x publish)
   - Mensaje nack'd pero no hay más consumers para reprocesar

3. **Edge cases no considerados**
   - Race conditions donde event se crea pero no se procesa
   - Bugs que dejan eventos en estado inconsistente

### Objetivo

Implementar **background task/job** que periódicamente:

- Identifica eventos "atascados" (CREATED/PENDING más allá de threshold)
- Los reprocesa automáticamente
- Registra intentos de recovery para auditoría

---

## 🎯 Diseño Propuesto

### Arquitectura

```
┌───────────────────────────────────────────────┐
│          Background Scheduler                  │
│         (APScheduler / Celery Beat)            │
└─────────────────┬─────────────────────────────┘
                  │
                  │ Every 5 minutes
                  │
                  ▼
┌───────────────────────────────────────────────┐
│      RecoverStuckEventsUseCase                │
│  1. Find CREATED/PENDING events > threshold   │
│  2. For each: republish to Redis              │
│  3. Update metadata (recovery_attempt_count)  │
└─────────────────┬─────────────────────────────┘
                  │
                  │ republish
                  │
                  ▼
┌───────────────────────────────────────────────┐
│         Redis: enqueue-event-subject          │
│     (Normal processing flow continues)        │
└───────────────────────────────────────────────┘
```

### Use Case: RecoverStuckEventsUseCase

```python
class RecoverStuckEventsUseCaseInput(BaseModel):
    threshold_minutes: int = Field(default=10)
    max_recovery_attempts: int = Field(default=3)
    batch_size: int = Field(default=50)

class RecoverStuckEventsUseCaseOutput(BaseModel):
    recovered_count: int
    failed_count: int
    skipped_count: int  # Exceeded max recovery attempts
    event_ids: list[UUID]

class RecoverStuckEventsUseCase(AsyncUseCase):
    def __init__(self, uow: IUnitOfWork, broker: RedisBroker):
        self.uow = uow
        self.broker = broker

    async def execute(
        self, input: RecoverStuckEventsUseCaseInput
    ) -> Result[RecoverStuckEventsUseCaseOutput, ErrorDetail]:
        async with self.uow:
            # 1. Find stuck events
            stuck_events = await self.uow.events.find_stuck_events(
                states=[EventState.CREATED, EventState.PENDING],
                threshold_minutes=input.threshold_minutes,
                limit=input.batch_size,
            )

            recovered = 0
            failed = 0
            skipped = 0
            event_ids = []

            for event in stuck_events:
                # 2. Check recovery attempts
                if event.recovery_attempt_count >= input.max_recovery_attempts:
                    skipped += 1
                    logger.warning(
                        f"Event {event.id} exceeded max recovery attempts "
                        f"({event.recovery_attempt_count})"
                    )
                    continue

                # 3. Republish to Redis
                try:
                    await self.broker.publish(
                        {
                            "event_id": str(event.id),
                            "name": event.name,
                            "is_recovery": True,  # Flag para auditoría
                        },
                        stream="enqueue-event-subject",
                    )

                    # 4. Update metadata
                    event.recovery_attempt_count += 1
                    event.last_recovery_at = datetime.utcnow()
                    await self.uow.events.save(event)

                    recovered += 1
                    event_ids.append(event.id)

                except Exception as e:
                    logger.error(f"Failed to recover event {event.id}: {e}")
                    failed += 1

            await self.uow.commit()

            return Ok(RecoverStuckEventsUseCaseOutput(
                recovered_count=recovered,
                failed_count=failed,
                skipped_count=skipped,
                event_ids=event_ids,
            ))
```

### Repository Method: find_stuck_events

```python
# En app/core/repository_event.py (interface)
@abstractmethod
async def find_stuck_events(
    self,
    states: list[EventState],
    threshold_minutes: int,
    limit: int = 100,
) -> list[Event]:
    """
    Find events in given states that are older than threshold.

    Args:
        states: List of states to filter (e.g., [CREATED, PENDING])
        threshold_minutes: Age threshold in minutes
        limit: Max events to return

    Returns:
        List of stuck events ordered by created_at (oldest first)
    """
    pass

# En app/infrastructure/db/repository_event.py (implementation)
async def find_stuck_events(
    self,
    states: list[EventState],
    threshold_minutes: int,
    limit: int = 100,
) -> list[Event]:
    threshold_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)

    stmt = (
        select(Event)
        .where(
            Event.state.in_(states),
            Event.created_at < threshold_time,
        )
        .order_by(Event.created_at.asc())
        .limit(limit)
    )

    result = await self.session.execute(stmt)
    return result.scalars().all()
```

### Scheduler Setup (APScheduler)

```python
# En app/infrastructure/scheduler/main.py (NEW)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

def setup_scheduler(broker: RedisBroker, session_factory):
    scheduler = AsyncIOScheduler()

    async def recover_stuck_events_job():
        """Periodic job to recover stuck events"""
        logger.info("Starting stuck events recovery job")

        async with session_factory() as session:
            async with AsyncSQLAlchemyUnitOfWork(session, owns_session=True) as uow:
                use_case = RecoverStuckEventsUseCase(uow=uow, broker=broker)
                result = await use_case.execute(
                    RecoverStuckEventsUseCaseInput(
                        threshold_minutes=10,  # 10 minutes threshold
                        max_recovery_attempts=3,
                        batch_size=50,
                    )
                )

                if result.is_ok():
                    output = result.unwrap()
                    logger.info(
                        f"Recovery job completed: "
                        f"recovered={output.recovered_count}, "
                        f"failed={output.failed_count}, "
                        f"skipped={output.skipped_count}"
                    )
                else:
                    logger.error(f"Recovery job failed: {result.unwrap_err()}")

    # Run every 5 minutes
    scheduler.add_job(
        recover_stuck_events_job,
        trigger=IntervalTrigger(minutes=5),
        id="recover_stuck_events",
        name="Recover Stuck Events Job",
        replace_existing=True,
    )

    return scheduler

# En app/infrastructure/api/main.py (startup)
@app.on_event("startup")
async def startup():
    # ... existing code ...

    # Start scheduler
    scheduler = setup_scheduler(broker, get_session_factory())
    scheduler.start()
    logger.info("Background scheduler started")
```

---

## 📊 Nuevas Columnas en Event Entity

### Migration: Add Recovery Metadata

```python
# En Event entity (app/core/entities.py)
class Event(SQLModel, table=True):
    # ... existing fields ...

    # Recovery metadata (NEW)
    recovery_attempt_count: int = Field(default=0)
    last_recovery_at: datetime | None = Field(default=None)
    is_recovered: bool = Field(default=False)  # Flag para auditoría
```

### Alembic Migration

```python
# migrations/versions/XXXX_add_recovery_metadata.py
def upgrade():
    op.add_column('event', sa.Column('recovery_attempt_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('event', sa.Column('last_recovery_at', sa.DateTime(), nullable=True))
    op.add_column('event', sa.Column('is_recovered', sa.Boolean(), nullable=False, server_default='false'))

def downgrade():
    op.drop_column('event', 'is_recovered')
    op.drop_column('event', 'last_recovery_at')
    op.drop_column('event', 'recovery_attempt_count')
```

---

## 🧪 Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_find_stuck_events(uow_factory, dbsession):
    """Test finding stuck events beyond threshold"""
    # Setup: Create events with different ages
    old_pending = Event(
        name="Old Pending",
        state=EventState.PENDING,
        created_at=datetime.utcnow() - timedelta(minutes=15),
    )
    recent_pending = Event(
        name="Recent Pending",
        state=EventState.PENDING,
        created_at=datetime.utcnow() - timedelta(minutes=5),
    )
    dbsession.add_all([old_pending, recent_pending])
    await dbsession.commit()

    # Test: Find stuck events (threshold=10min)
    async with uow_factory() as uow:
        stuck = await uow.events.find_stuck_events(
            states=[EventState.PENDING],
            threshold_minutes=10,
        )

    # Assert: Only old event returned
    assert len(stuck) == 1
    assert stuck[0].id == old_pending.id


@pytest.mark.asyncio
async def test_recover_stuck_events_use_case(uow_mock, broker_mock):
    """Test recovery use case logic"""
    stuck_event = Event(
        name="Stuck",
        state=EventState.PENDING,
        recovery_attempt_count=0,
    )
    uow_mock.events.find_stuck_events = AsyncMock(return_value=[stuck_event])

    use_case = RecoverStuckEventsUseCase(uow=uow_mock, broker=broker_mock)
    result = await use_case.execute(RecoverStuckEventsUseCaseInput())

    assert result.is_ok()
    output = result.unwrap()
    assert output.recovered_count == 1
    assert stuck_event.recovery_attempt_count == 1
    broker_mock.publish.assert_called_once()
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_recovery_job_end_to_end(uow_factory, broker, dbsession):
    """Test full recovery flow: find → republish → process"""
    # Step 1: Create stuck event
    stuck_event = Event(
        name="Stuck Event",
        state=EventState.PENDING,
        created_at=datetime.utcnow() - timedelta(minutes=20),
    )
    dbsession.add(stuck_event)
    await dbsession.commit()

    # Step 2: Run recovery job
    async with uow_factory() as uow:
        use_case = RecoverStuckEventsUseCase(uow=uow, broker=broker)
        result = await use_case.execute(RecoverStuckEventsUseCaseInput())

    # Step 3: Verify republished
    assert result.is_ok()
    assert result.unwrap().recovered_count == 1

    # Step 4: Verify metadata updated
    await dbsession.refresh(stuck_event)
    assert stuck_event.recovery_attempt_count == 1
    assert stuck_event.last_recovery_at is not None
```

---

## 📊 Monitoring & Alerting

### Métricas a Trackear

| Métrica                          | Descripción                        | Alert Threshold |
| -------------------------------- | ---------------------------------- | --------------- |
| `stuck_events_count`             | # eventos atascados por run        | > 10            |
| `recovery_success_rate`          | % recoveries exitosos              | < 90%           |
| `recovery_job_duration`          | Tiempo de ejecución del job        | > 60s           |
| `max_recovery_attempts_exceeded` | # eventos con 3+ recovery attempts | > 5             |

### Dashboard Panel (Grafana)

```promql
# Events stuck for > 10 minutes
count(event_state{state=~"CREATED|PENDING"} and time() - event_created_at > 600)

# Recovery success rate (last 1h)
rate(recovery_success_total[1h]) / rate(recovery_attempts_total[1h])
```

---

## 🚦 Rollout Plan

### Phase 1: Repository Method (1 day)

1. Add `find_stuck_events` to EventRepository interface
2. Implement in AsyncSQLAlchemyEventRepository
3. Unit tests para repository method
4. Functional tests para query logic

### Phase 2: Use Case (1 day)

1. Implement RecoverStuckEventsUseCase
2. Add recovery metadata columns to Event entity
3. Alembic migration
4. Unit tests para use case logic

### Phase 3: Scheduler Setup (1 day)

1. Add APScheduler dependency
2. Create scheduler module
3. Integrate with FastAPI startup
4. Integration tests para full flow

### Phase 4: Monitoring (1 day)

1. Add metrics collection
2. Create Grafana dashboard
3. Setup alerts for anomalies
4. Documentation para on-call

### Phase 5: Production Rollout (1 day)

1. Deploy to staging
2. Monitor for 24h
3. Adjust thresholds based on metrics
4. Deploy to production

---

## ⚠️ Consideraciones

### Performance

- **Batch Size**: Limitar a 50 eventos por run para evitar overhead
- **Frequency**: 5 minutos es suficiente (no real-time critical)
- **Query Optimization**: Index en `(state, created_at)` para find_stuck_events

### Edge Cases

1. **Recovery loop**: Si evento sigue fallando, skip after 3 attempts
2. **Concurrent processing**: Use row-level locks para evitar doble processing
3. **State transitions during recovery**: Check state antes de republish

### Rollback Plan

Si recovery job causa problemas:

1. Disable scheduler via feature flag
2. Mark stuck events manualmente
3. Investigate root cause
4. Fix and re-enable

---

## 🔗 Related Documentation

- [RETRY_STRATEGY.md](RETRY_STRATEGY.md) - Retry logic con exponential backoff
- [TRANSACTION_PATTERN.md](TRANSACTION_PATTERN.md) - Handler-managed transactions
- [Agents.md](../Agents.md) - Development workflow

---

## 📋 Acceptance Criteria

- [ ] RecoverStuckEventsUseCase implemented
- [ ] find_stuck_events repository method working
- [ ] APScheduler configured (run every 5min)
- [ ] Recovery metadata columns added to Event
- [ ] Unit tests: 100% coverage para use case
- [ ] Integration tests: Full recovery flow tested
- [ ] Monitoring dashboard created
- [ ] Documentation updated (Agents.md)

---

**Created**: January 3, 2026  
**Estimated Start**: Q1 2026  
**Owner**: TBD  
**Stakeholders**: Backend team, DevOps
