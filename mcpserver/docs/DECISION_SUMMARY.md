# Executive Summary: Transaction Architecture Decision

**Date**: 2026-01-03  
**Status**: ✅ DECISION MADE - Ready for Implementation  
**Stakeholder Approval**: Pending peer review

---

## 🎯 The Question You Raised

> "¿Debemos reutilizar `UnitOfWork` para coordinar transacciones entre varios use cases?"

**Answer**: ✅ **YES** - But we need to change WHO manages the transaction lifecycle.

---

## 🔴 Problem with Current Code

```python
# Line 138 in app/core/usecases/event_usecases.py
async with self.uow:  # ❌ UseCase opens context
    evt = Event(...)
    return await self.uow.events.save_or_resolve_one(evt)
```

**Issues**:

1. ❌ Cannot coordinate `save + publish` in one atomic transaction
2. ❌ Cannot compose 2+ use cases (enqueue + process) together
3. ❌ Violates Clean Architecture (UseCase manages infrastructure concern)

---

## 🟢 Solution: Handler Orchestrates, UseCase Executes

### Simple Diagram

```
┌─────────────────────────────────────────┐
│ Handler (Infrastructure)                │
│ ┌─────────────────────────────────────┐ │ ← OPENS TRANSACTION
│ │ UseCase1 + UseCase2 + Publishing    │ │
│ │ └─ All within SAME transaction      │ │
│ └─────────────────────────────────────┘ │
│ COMMIT or ROLLBACK (all or nothing)     │ ← CLOSES TRANSACTION
└─────────────────────────────────────────┘
```

### Code Example

```python
# ❌ BEFORE: UseCase manages transaction
class EnqueueEventUseCase:
    async def execute(self, input):
        async with self.uow:  # Opens context
            evt = Event(...)
            return await self.uow.events.save_or_resolve_one(evt)
        # Closes context + commits

# ✅ AFTER: Handler manages transaction
class EnqueueEventUseCase:
    async def execute(self, input):
        # NO async with - assumes caller manages transaction
        evt = Event(...)
        return await self.uow.events.save_or_resolve_one(evt)

# Handler manages orchestration
@EnqueueEventSubscriber
async def handle_enqueue_event(...):
    async with AsyncSQLAlchemyUnitOfWork(session) as uow:  # Opens
        # 1. Enqueue
        usecase = EnqueueEventUseCase(uow)
        result = await usecase.execute(event)

        # 2. Publish (same transaction)
        if result.is_ok():
            await broker.publish(...)  # Inside transaction!

        # 3. Auto-commit on exit (or rollback if error)
    # Closes + commits
```

---

## ✅ Benefits

| Benefit           | Impact                                                     |
| ----------------- | ---------------------------------------------------------- |
| **Atomicity**     | `save + publish` guaranteed to succeed/fail together       |
| **Composability** | Run 2+ use cases in single transaction                     |
| **Testability**   | UseCase tests don't need transaction context               |
| **Architecture**  | Clean separation: Handler orchestrates, UseCase executes   |
| **Flexibility**   | Different handlers can have different transaction policies |

---

## 📋 What Changes

### Core Layer (Business Logic)

```python
# EnqueueEventUseCase
# ProcessEventUseCase
# Any future use case
# ➜ Remove: async with self.uow
# ➜ Keep: All business logic
# ➜ Assume: Caller manages transaction
```

### Infrastructure Layer (Orchestration)

```python
# app/infrastructure/redis/main.py
# handle_enqueue_event()
# handle_processing_event_queue()
# ➜ Add: async with AsyncSQLAlchemyUnitOfWork(...) as uow
# ➜ Orchestrate: UseCase + side-effects in one transaction
# ➜ Guarantee: Atomicity
```

### Tests

```python
# Unit Tests (unchanged complexity)
async def test_enqueue_event():
    uow_mock = MagicMock()
    uc = EnqueueEventUseCase(uow_mock)
    result = await uc.execute(input)  # No context needed
    assert result.is_ok()

# Functional Tests (handler manages context)
async def test_enqueue_handler_atomic(uow_factory):
    async with uow_factory() as uow:
        uc = EnqueueEventUseCase(uow)
        result = await uc.execute(input)
        assert result.is_ok()
        # Both operations committed atomically
```

---

## 🗺️ Implementation Roadmap

### Phase 1: Refactor Core UseCases (1 day)

- [ ] Remove `async with self.uow:` from EnqueueEventUseCase
- [ ] Remove `async with self.uow:` from ProcessEventUseCase
- [ ] Add documentation: "Caller must manage transaction"

### Phase 2: Update Infrastructure (1 day)

- [ ] Add `async with` wrapper in handle_enqueue_event
- [ ] Add `async with` wrapper in handle_processing_event_queue
- [ ] Implement error handling (rollback/ack/nack logic)

### Phase 3: Migrate Tests (2 days)

- [ ] Unit tests: Verify no transaction context needed
- [ ] Functional tests: Verify atomicity with new pattern
- [ ] Integration tests: Verify full handler flow

### Phase 4: Documentation (1 day)

- [ ] Update development guide
- [ ] Create examples for new use cases
- [ ] Document transaction ownership policy

**Total**: ~5 days work

---

## 🎓 Key Architectural Insight

**Old Model** (❌ Problematic):

```
UseCase owns transaction scope
  └─ Forces context manager in UseCase
     └─ Prevents composition
        └─ Makes atomicity hard
```

**New Model** (✅ Correct):

```
Handler owns transaction scope
  └─ UseCase is transaction-agnostic
     └─ Enables composition
        └─ Guarantees atomicity
```

---

## ✨ Why This Matters for Mejora #2

**Mejora #2**: Publish event to `processing-event-subject` after enqueue

**With OLD pattern**:

```
Handler calls UseCase.execute()
  └─ UseCase opens transaction
     ├─ Saves event
     └─ COMMITS
Handler tries to publish
  └─ Outside transaction
     └─ If publish fails: Event already committed (DATA INCONSISTENCY)
```

**With NEW pattern**:

```
Handler opens transaction
  ├─ UseCase.execute() saves event
  ├─ Handler publishes to processing-subject
  └─ COMMITS all together
     └─ Guaranteed atomicity
```

---

## 📊 Decision Matrix

| Criteria            | CURRENT  | PROPOSED |
| ------------------- | -------- | -------- |
| Atomic save+publish | ❌       | ✅       |
| Composable          | ❌       | ✅       |
| Clean Arch          | ❌       | ✅       |
| Testable            | ⚠️       | ✅       |
| Effort              | 0 (done) | 5 days   |

---

## 🔗 Documentation Files

1. **[ANALYSIS_UOW_TRANSACTION_DESIGN.md](ANALYSIS_UOW_TRANSACTION_DESIGN.md)**

   - Detailed analysis of 4 alternatives
   - Pros/cons of each approach
   - Why Alternative A is recommended

2. **[DESIGN_COMPARISON_VISUAL.md](DESIGN_COMPARISON_VISUAL.md)**

   - Visual diagrams
   - Sequence flows
   - Side-by-side comparisons

3. **[ADR_TRANSACTION_ORCHESTRATION.md](ADR_TRANSACTION_ORCHESTRATION.md)**
   - Formal Architecture Decision Record
   - Implementation plan
   - Testing implications

---

## ✅ Ready to Proceed?

**Current Status**: ✅ Analysis complete, Decision made

**Next Steps**:

1. ✅ Peer review (you are doing this now)
2. ⏳ Get stakeholder approval
3. ⏳ Implement Phase 1-4
4. ⏳ Implement Mejora #2 (with correct transaction pattern)
5. ⏳ Extend to other use cases

---

## 💬 Questions to Answer

1. **Do you agree with Alternativa A** (Handler-managed transactions)?
2. **Should we proceed with the 4-phase implementation plan?**
3. **Any concerns with removing `async with self.uow` from use cases?**
4. **Ready to tackle Mejora #2 with this new pattern?**
