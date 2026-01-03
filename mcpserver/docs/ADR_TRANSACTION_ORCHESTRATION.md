# ADR: Transactional Orchestration in Event Processing Pipeline

**Status**: PROPOSED  
**Date**: 2026-01-03  
**Deciders**: Development Team  
**Affected by**: Mejora #2 (Publish to processing), Future use case composition  

---

## 🎯 Problem Statement

Currently, `EnqueueEventUseCase` opens its own transaction context:

```python
async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
    async with self.uow:  # ❌ UseCase manages transaction
        evt = Event(...)
        return await self.uow.events.save_or_resolve_one(evt)
```

This creates three critical issues:

1. **Atomicity**: Cannot coordinate save + publish in same transaction
   - Event saved and committed ✓
   - If publish fails, already committed (data inconsistency)
   - If publish succeeds, but handler crashes before ack, duplicate processing

2. **Composability**: Cannot run 2+ use cases in single transaction
   - Each opens its own transaction independently
   - No transactional isolation across multiple operations
   - Tests cannot verify atomic multi-step operations

3. **Separation of Concerns Violation**:
   - UseCase handles both business logic AND transaction lifecycle
   - Makes testing and composition difficult
   - Violates Single Responsibility Principle

---

## 🔄 Proposed Solution

**Handler (Infrastructure Layer) manages transaction orchestration.**  
**UseCase (Core Layer) contains only business logic.**

```python
# Core Layer - Pure Business Logic
class EnqueueEventUseCase(AsyncUseCase[...]):
    async def execute(self, input: EnqueuedEventUseCaseInput) -> Result[...]:
        # ✅ NO: async with self.uow
        # ✅ Assumes transaction already open by caller
        evt = Event(...)
        return await self.uow.events.save_or_resolve_one(evt)

# Infrastructure Layer - Orchestration & Transactional Guarantees
@EnqueueEventSubscriber
async def handle_enqueue_event(..., session: AsyncSession = Depends(get_session)) -> None:
    try:
        # ✅ Handler OPENS transaction
        async with AsyncSQLAlchemyUnitOfWork(session, owns_session=False) as uow:
            usecase = EnqueueEventUseCase(uow)
            
            # Step 1: Save event
            result = await usecase.execute(event)
            
            # Step 2: Publish for processing (same transaction)
            if result.is_ok():
                await broker.publish(
                    {"event_id": str(result.unwrap().id), ...},
                    stream="processing-event-subject"
                )
            # ✅ Commit/Rollback on __aexit__ (ATOMIC)
            
            await msg.ack() if result.is_ok() else await msg.nack()
    except Exception as e:
        await msg.nack()
```

---

## 💡 Why This Design

### 1. Atomicity Guarantee
```
┌──────────────────────────────────────┐
│ Transaction (Handler-managed)        │
├──────────────────────────────────────┤
│ ├─ UseCase.execute()                │
│ │  └─ save(event)                  │
│ │                                   │
│ ├─ broker.publish()                 │
│ │  └─ publish(processing)          │
│ │                                   │
│ └─ COMMIT or ROLLBACK (all or none) │
└──────────────────────────────────────┘
```

If publish fails → entire transaction rolls back → data consistency preserved.

### 2. Use Case Composition
```python
async with AsyncSQLAlchemyUnitOfWork(session) as uow:
    # Multiple use cases, single transaction
    uc1 = EnqueueEventUseCase(uow)
    result1 = await uc1.execute(input1)
    
    uc2 = ProcessEventUseCase(uow)
    result2 = await uc2.execute(input2)
    
    # If either fails → both rollback
```

### 3. Clean Architecture Separation
```
Core (Domain Logic):
├─ Entities: Event, EventState, etc.
├─ Interfaces: UnitOfWork (ABC)
└─ UseCases: EnqueueEventUseCase
            └─ execute(input) → Result
            └─ NO transaction management

Infrastructure (Implementation):
├─ API: Routers, Handlers
├─ DB: Repositories, UnitOfWork impl
├─ Redis: Broker, Subscribers
└─ handlers/main.py
   ├─ OPEN transaction
   ├─ ORCHESTRATE use cases
   ├─ HANDLE infrastructure concerns
   └─ CLOSE transaction
```

### 4. SOLID Principles Adherence
- **S**RP: Each class has one reason to change
- **O**CP: Easy to add new use cases without modifying orchestration
- **L**SP: All use cases work with same interface
- **I**SP: UseCase only needs UoW, not transaction handling
- **D**IP: Depends on abstractions (UnitOfWork), not concretions

---

## ⚖️ Tradeoffs

### Advantages ✅
1. **Atomic operations**: Save + publish guaranteed
2. **Composable**: Multiple use cases in one transaction
3. **Testable**: Use cases can be unit tested without transaction context
4. **Clear responsibilities**: Handler orchestrates, UseCase executes logic
5. **Flexible**: Different handlers can apply different transaction policies

### Disadvantages ⚠️
1. **Assumptions**: UseCase assumes transaction already open (requires documentation)
2. **Runtime errors**: If handler forgets to open transaction → error at runtime
3. **Migration effort**: All existing use cases need refactoring
4. **Learning curve**: New developers must understand ownership model

---

## 🧪 Testing Implications

### Unit Test (UseCase logic isolated)
```python
async def test_enqueue_event_happy_path():
    """UseCase logic, not transaction lifecycle"""
    # Setup: Mock UoW
    uow_mock = MagicMock()
    uow_mock.events.save_or_resolve_one = AsyncMock(return_value=Ok(event))
    
    # Execute: UseCase does NOT open context
    uc = EnqueueEventUseCase(uow_mock)
    result = await uc.execute(input_data)
    
    # Verify
    assert result.is_ok()
    uow_mock.events.save_or_resolve_one.assert_called_once()
```

### Functional Test (Handler orchestration + transaction)
```python
async def test_enqueue_then_publish_atomic(uow_factory):
    """Handler manages transaction, UseCase executes within it"""
    async with uow_factory() as uow:
        uc = EnqueueEventUseCase(uow)
        result = await uc.execute(input_data)
        
        assert result.is_ok()
        
        # Both operations in same transaction
        await broker.publish({...}, stream="processing-event-subject")
    
    # Verify in DB
    assert event_exists_in_db()
```

### Integration Test (Full handler flow)
```python
async def test_handle_enqueue_event_end_to_end():
    """Full handler with Redis/DB/Transaction"""
    # Handler opens transaction + orchestrates
    # Handler publishes + commits
    # Handler acks on success, nacks on failure
```

---

## 🚀 Implementation Plan

### Phase 1: Refactor Core UseCases
**Timeline**: 1 day  
**Files**:
- `app/core/usecases/event_usecases.py`
  - Remove `async with self.uow:` from all use cases
  - Add docstring: "Caller must manage transaction"

### Phase 2: Update Infrastructure Handlers
**Timeline**: 1 day  
**Files**:
- `app/infrastructure/redis/main.py`
  - Add `async with AsyncSQLAlchemyUnitOfWork(...) as uow:` wrapper
  - Update error handling to rollback/ack/nack correctly

### Phase 3: Migrate Tests
**Timeline**: 2 days  
**Files**:
- `tests/unit/test_enqueue_event_usecase_unit.py`
  - Remove context manager expectations
  - Tests run without transaction context
  
- `tests/functional/test_enqueue_event_usecase_functional.py`
  - Add transaction context in fixtures
  - Verify atomicity where applicable

### Phase 4: Documentation
**Timeline**: 1 day  
**Files**:
- Update development guide
- Add transaction ownership documentation
- Create examples for new use case developers

---

## 📊 Affected Components

```
┌──────────────────────────────────────┐
│ app/core/usecases/                   │
├──────────────────────────────────────┤
│ • EnqueueEventUseCase                │ (MODIFY: remove async with)
│ • ProcessEventUseCase                │ (MODIFY: remove async with)
│ • TransitionEventUseCase             │ (if exists)
└──────────────────────────────────────┘
                  │
                  │ depends on
                  ▼
┌──────────────────────────────────────┐
│ app/infrastructure/redis/main.py    │
├──────────────────────────────────────┤
│ • handle_enqueue_event              │ (MODIFY: add async with)
│ • handle_processing_event_queue     │ (MODIFY: add async with)
└──────────────────────────────────────┘
                  │
                  │ uses
                  ▼
┌──────────────────────────────────────┐
│ app/infrastructure/db/unit_of_work.py│
├──────────────────────────────────────┤
│ • AsyncSQLAlchemyUnitOfWork         │ (NO CHANGE needed)
│ • owns_session logic                │ (already in place)
└──────────────────────────────────────┘
```

---

## ✅ Decision

**APPROVED**: Implement ALTERNATIVE A - Handler-managed transaction orchestration.

### Rationale
1. Enables atomicity for event enqueue + publish workflow
2. Allows future composition of multiple use cases
3. Follows Clean Architecture and SOLID principles
4. Improves testability
5. Clear separation of concerns

### Next Steps
1. Obtain stakeholder buy-in
2. Create refactoring PR
3. Implement per phase plan
4. Update documentation
5. Proceed with Mejora #2 (Publish to processing)

---

## 📚 References

- [ANALYSIS_UOW_TRANSACTION_DESIGN.md](ANALYSIS_UOW_TRANSACTION_DESIGN.md) - Detailed alternatives analysis
- [DESIGN_COMPARISON_VISUAL.md](DESIGN_COMPARISON_VISUAL.md) - Visual comparisons
- [IMPROVEMENTS_ROADMAP.md](IMPROVEMENTS_ROADMAP.md) - Feature roadmap
- [Agents.md - Development Workflow](../Agents.md) - Development practices
