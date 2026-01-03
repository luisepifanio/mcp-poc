# 🔄 Transaction Pattern Documentation

**Date**: January 3, 2026  
**Status**: ✅ Implemented and Validated  
**Pattern**: Handler-Managed Transaction Orchestration

---

## 📋 Quick Reference

### The Pattern

```python
# Infrastructure Layer (Handler orchestrates)
@EventSubscriber
async def handle_enqueue_event(
    event: EnqueuedEventUseCaseInput,
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    # ✅ Handler OPENS transaction context
    async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:

        # ✅ Instantiate use case with UoW
        usecase = EnqueueEventUseCase(uow)

        # ✅ UseCase executes WITHOUT context manager
        result = await usecase.execute(event)

        # ✅ Check result and decide
        if result.is_ok():
            event_saved = result.unwrap()

            # ✅ Publish within SAME transaction (atomic)
            await broker.publish({...}, stream="processing-event-subject")

            await msg.ack()
        else:
            await msg.nack()

    # ✅ Transaction COMMITS/ROLLBACKS on exit
```

```python
# Core Layer (UseCase is pure logic)
class EnqueueEventUseCase(AsyncUseCase[...]):
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(
        self, input: EnqueuedEventUseCaseInput
    ) -> Result[EnqueuedEventUseCaseOutput, ErrorDetail]:
        # ✅ NO context manager here
        # ✅ Assumes caller manages transaction
        # See: docs/TRANSACTION_PATTERN.md

        # Pure business logic
        evt = Event(...)
        return await self.uow.events.save_or_resolve_one(evt)
```

---

## 🎯 Key Principles

### 1. **Session Ownership** (`owns_session` parameter)

```python
# Handler-created UoW (handler owns session)
async with AsyncSQLAlchemyUnitOfWork(session, owns_session=True) as uow:
    # UoW will close session on exit
    pass

# Dependency-injected UoW (FastAPI manages session)
async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
    # Session stays open after UoW exits
    # FastAPI Depends will close it
    pass
```

**Rule**:

- `owns_session=False` when session comes from `Depends(get_session)`
- `owns_session=True` when handler creates session directly

### 2. **Handler Responsibilities**

| Responsibility       | Where                    | Why                             |
| -------------------- | ------------------------ | ------------------------------- |
| **Open transaction** | Handler `async with`     | Orchestrates multiple use cases |
| **Create use case**  | Handler (inside context) | Ensures UseCase has active TX   |
| **Execute use case** | UseCase (pure logic)     | Business logic isolated         |
| **Publish events**   | Handler (inside context) | Guarantees atomicity            |
| **Commit/Rollback**  | Handler `__aexit__`      | Atomic operation                |
| **Message ack/nack** | Handler (after context)  | Acknowledge only after commit   |

### 3. **UseCase Assumptions**

Every UseCase should have a docstring stating:

```python
class MyUseCase(AsyncUseCase[Input, Result[Output, Error]]):
    """
    Business logic for MyDomain.

    ASSUMES: Caller manages transaction context.
    - Do NOT use 'async with self.uow'
    - Caller opens UoW context before instantiating this use case
    - All database operations within same transaction

    See: docs/TRANSACTION_PATTERN.md
    """
```

---

## 🔍 Detailed Examples

### Example 1: Simple Event Enqueue

```python
# Handler in infrastructure/redis/main.py
@EnqueueEventSubscriber
async def handle_enqueue_event(
    event: EnqueuedEventUseCaseInput,
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        logger.info(f"Event received: {event}")

        # Step 1: Open transaction context
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            # Step 2: Create use case
            usecase = EnqueueEventUseCase(uow)

            # Step 3: Execute (no context manager in usecase)
            result = await usecase.execute(event)

            # Step 4: Check result
            match result:
                case Ok(value):
                    logger.info(f"Event enqueued: {value}")
                    # Step 5: Publish (within transaction)
                    await broker.publish(
                        {
                            "event_id": str(value.id),
                            "name": value.name,
                            "state": value.state.value,
                        },
                        stream="processing-event-subject"
                    )
                    # Step 6: Ack message
                    await msg.ack()
                case Err(error):
                    logger.error(f"Enqueue failed: {error}")
                    await msg.nack()

        # Step 7: On exit, transaction commits
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await msg.nack()
```

### Example 2: Multi-UseCase Composition

```python
# Handler orchestrating multiple use cases in single transaction
async def handle_complex_event(
    event: ComplexEventInput,
    msg: RedisMessage,
    session: AsyncSession = Depends(get_session),
) -> None:
    try:
        # Open SINGLE transaction for both use cases
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            # UseCase 1: Enqueue event
            enqueue_uc = EnqueueEventUseCase(uow)
            result1 = await enqueue_uc.execute(event.to_input())

            if not result1.is_ok():
                raise ValueError(f"Enqueue failed: {result1}")

            saved_event = result1.unwrap()

            # UseCase 2: Process event (reuse same UoW)
            process_uc = ProcessEventUseCase(uow)
            result2 = await process_uc.execute(
                ProcessEventInput(event_id=saved_event.id)
            )

            if not result2.is_ok():
                # Both rollback together
                raise ValueError(f"Process failed: {result2}")

            # Both succeed = publish
            await broker.publish({...}, stream="...")
            await msg.ack()

        # Single COMMIT: both save + process + publish atomic
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await msg.nack()
        # Single ROLLBACK: both operations undone
```

### Example 3: Testing the Pattern

```python
# tests/functional/test_handler_transaction_orchestration.py

@pytest.mark.asyncio
async def test_handler_pattern_transaction_orchestration(
    dbsession: AsyncSession,
) -> None:
    """Handler manages transaction, UseCase executes without context."""
    event_input = EnqueuedEventUseCaseInput(
        name="TestEvent",
        external_uuid=uuid4(),
        payload={"test": "data"},
    )

    # Simulate what the handler does
    async with AsyncSQLAlchemyUnitOfWork(dbsession, owns_session=False) as uow:
        # Handler instantiates usecase
        usecase = EnqueueEventUseCase(uow)

        # Handler executes (usecase has NO async with)
        result = await usecase.execute(event_input)

        assert result.is_ok()
        # At this point: transaction is OPEN

    # After exit: transaction COMMITS
    # Verify persistence
    stmt = select(Event).where(Event.name == "TestEvent")
    db_result = await dbsession.execute(stmt)
    assert db_result.scalar_one_or_none() is not None
```

---

## 🚨 Common Mistakes

### ❌ WRONG: UseCase creates its own context

```python
class BadUseCase(AsyncUseCase):
    async def execute(self, input):
        async with self.uow:  # ❌ WRONG
            return save(input)
```

**Problem**: Can't compose with other use cases in same transaction

### ❌ WRONG: Handler uses owns_session=True with Depends

```python
@handler
async def bad_handler(session = Depends(get_session)):
    async with AsyncSQLAlchemyUnitOfWork(session, owns_session=True) as uow:  # ❌ WRONG
        # Handler tries to close session that FastAPI will close
        pass
```

**Problem**: Double-close error, FastAPI will try to close already-closed session

### ❌ WRONG: Handler ack/nack inside context

```python
@handler
async def bad_handler(msg: RedisMessage, session = Depends(get_session)):
    async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
        result = await usecase.execute(...)
        await msg.ack()  # ❌ WRONG (inside context)
```

**Problem**: Message acked before commit completes

### ✅ RIGHT: Everything in order

```python
@handler
async def good_handler(msg: RedisMessage, session = Depends(get_session)):
    try:
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            result = await usecase.execute(...)
            if result.is_ok():
                await broker.publish(...)  # ✅ Inside context
        # ✅ Here: transaction committed
        await msg.ack()  # ✅ After context
    except:
        await msg.nack()  # ✅ After context
```

---

## 📋 Checklist for Creating New UseCase

When creating a new use case, follow this checklist:

```markdown
- [ ] Inherit from AsyncUseCase[Input, Result[Output, Error]]
- [ ] Add docstring with "ASSUMES: Caller manages transaction"
- [ ] Do NOT use 'async with self.uow' in execute()
- [ ] All database operations via self.uow (injected in **init**)
- [ ] Return Result type (Ok or Err)
- [ ] Add unit tests with mock UoW (no context manager)
- [ ] Add functional tests with real UoW in context
- [ ] Create handler that wraps with AsyncSQLAlchemyUnitOfWork
- [ ] Handler includes publish/ack logic within context
- [ ] Add handler integration test
```

### Template for New UseCase

```python
from app.core.usecase import AsyncUseCase
from app.core.unit_of_work import UnitOfWork
from result import Ok, Err, Result

class MyUseCase(AsyncUseCase[MyInput, Result[MyOutput, ErrorDetail]]):
    """
    Business logic for MyDomain.

    ASSUMES: Caller manages transaction context.
    - Do NOT use 'async with self.uow'
    - Caller opens UoW context before instantiating this use case
    - All database operations within same transaction

    See: docs/TRANSACTION_PATTERN.md
    """

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def execute(
        self, input: MyInput
    ) -> Result[MyOutput, ErrorDetail]:
        """
        Execute MyDomain business logic.

        Args:
            input: MyInput with required fields

        Returns:
            Result[MyOutput, ErrorDetail]
        """
        # Validate input
        try:
            RootModel[MyInput](input)
        except ValidationError as exc:
            return Err(ErrorDetail(...))

        # Business logic (no async with)
        entity = MyEntity(...)
        op_result = await self.uow.my_repo.save(entity)

        # Map to output
        return op_result.and_then(
            lambda saved: Ok(self.as_output(saved))
        )

    def as_output(self, entity: MyEntity) -> MyOutput:
        return MyOutput(...)
```

---

## 📊 When to Use This Pattern

| Scenario                         | Recommendation                |
| -------------------------------- | ----------------------------- |
| Single UseCase, single operation | ✅ Use pattern                |
| Multiple UseCases in one handler | ✅ Use pattern (compose)      |
| Testing UseCase logic            | ✅ Wrap in context in test    |
| FastAPI endpoint                 | ✅ Use pattern (with Depends) |
| Worker/Job handler               | ✅ Use pattern                |
| CLI command                      | ✅ Use pattern                |

---

## 🔗 Related Documentation

- [ADR_TRANSACTION_ORCHESTRATION.md](ADR_TRANSACTION_ORCHESTRATION.md) - Architectural decision
- [DECISION_SUMMARY.md](DECISION_SUMMARY.md) - Executive summary
- [app/core/usecases/](../app/core/usecases/) - UseCase implementations
- [app/infrastructure/redis/main.py](../app/infrastructure/redis/main.py) - Handler examples
- [tests/functional/test_handler_transaction_orchestration.py](../tests/functional/test_handler_transaction_orchestration.py) - Test examples

---

## ❓ FAQ

**Q: Why remove `async with self.uow` from UseCase?**  
A: Enables composition - multiple UseCases in single transaction. Handler orchestrates, UseCase executes.

**Q: What if UseCase needs its own transaction?**  
A: Don't use this pattern for that use case. Keep `async with self.uow` if it's standalone. Pattern is for composable, orchestrated use cases.

**Q: How do I test UseCase without context manager?**  
A: Wrap it in context in the test. Handler does the same in production.

**Q: What happens if publish fails?**  
A: Everything rolls back (save + publish). This is the guarantee of handler-managed transactions.

**Q: Can I have nested contexts?**  
A: No. Handler opens ONE context. All UseCases share it. One commit, one rollback.

---

**Last Updated**: January 3, 2026  
**Next Review**: After Mejora #2 implementation
