# 📊 Code Coverage & Technical Debt Analysis

**Fecha**: 10 enero 2026  
**Current Coverage**: 82.61% (Threshold: 85%)  
**Gap**: -2.39% (34 statements uncovered + 32 branch coverage gaps)

---

## 1️⃣ Coverage Breakdown by Module

### 🔴 LOW COVERAGE (< 70%)

| Module | Coverage | Statements | Missing | Priority |
|--------|----------|------------|---------|----------|
| `app/main.py` | 0% | 1 | 1 | 🔴 Remove |
| `app/infrastructure/redis/main.py` | 41% | 77 | 42 | 🔴 High |
| `app/core/usecases/event_usecases.py` | 46% | 122 | 57 | 🔴 High |
| `app/infrastructure/db/connection.py` | 79% | 28 | 6 | 🟡 Medium |
| `app/infrastructure/db/models/default.py` | 73% | 20 | 4 | 🟡 Low |
| `app/core/processor_registry.py` | 72% | 41 | 10 | 🟡 Medium |
| `app/infrastructure/processors/sync_processors.py` | 79% | 118 | 17 | 🟡 Medium |

### 🟢 GOOD COVERAGE (> 85%)

- `app/core/repository_event.py`: 95% ✅
- `app/infrastructure/db/unit_of_work.py`: 95% ✅
- `app/infrastructure/redis/dlq_handler.py`: 95% ✅
- `app/core/usecases/neo_event_usecase.py`: 89% ✅
- `app/core/errors.py`: 96% ✅

---

## 2️⃣ Modules Analysis: Dead Code & Unused Components

### 📦 `app/main.py` - **CANDIDATE FOR REMOVAL**

```python
# File: app/main.py (1 statement, 0% coverage)
# Content:
logger = logging.getLogger(__name__)
```

**Assessment**:
- ✗ No usage found in codebase
- ✗ Not imported anywhere
- ✗ No tests
- ✓ Can be removed safely

**Impact**: -1 uncovered statement → Improves coverage by 0.08%

**Effort**: TRIVIAL (< 5 min)

---

### 📦 `app/core/usecases/event_usecases.py` - **DEPRECATED USE CASE**

```python
# Lines 215-337: ProcessEventUseCase (LEGACY)
class ProcessEventUseCase(AsyncUseCase[...]):
    """DEPRECATED: Use ProcessEventIdealUseCase instead"""
```

**Assessment**:
- ✗ Not used in Redis handlers (uses ProcessEventIdealUseCase)
- ✗ Covered by tests but tests are FAILING (12 failed in redis_handlers_unit.py)
- ✓ ProcessEventIdealUseCase is the canonical replacement
- 📍 Contains ~120 lines, ~46% coverage

**Unused Methods in File**:
1. `transition_event()` - only used internally by ProcessEventUseCase
2. `ProcessEventUseCase` class entirely (replace with ProcessEventIdealUseCase)

**Impact**: Removing would remove ~100 uncovered lines (estimated +8% coverage improvement)

**Effort**: MEDIUM (2-3 hours)
- Delete ProcessEventUseCase class
- Delete transition_event helper
- Update/delete associated tests
- Verify no imports remain

**Blocking**: Current FAILING TESTS in concurrency module

---

### 📦 `app/infrastructure/redis/main.py` - **LOW COVERAGE (41%)**

```
Missing Coverage Lines: 63-69, 76-81, 116-182, 216-238
```

**Assessment**:
- ✓ Critical handler code (enqueue + processing)
- ✗ 42 statements untested
- 📍 Issue: Tests skip actual Redis/FastStream integration

**Untested Sections**:
1. **handle_enqueue_event** (Lines 116-182): Retry logic paths
   - Success path (msg.ack)
   - Error paths (msg.nack)
   - Retry exhaustion
   
2. **handle_processing_event_queue** (Lines 216-238): Error handling
   - Exception catching
   - Unexpected errors
   - Message nack paths

**Why Low?**: Tests mock the handler dependencies; they don't test actual Redis publishing/subscribing

**Impact**: Adding 8-10 functional tests → +15-20% coverage on this file

**Effort**: MEDIUM (3-4 hours)
- Create integration tests with in-memory Redis
- Test actual FastStream subscriber behavior
- Test retry strategy timing
- Test DLQ publishing

---

### 📦 `app/core/usecases/event_usecases.py` - **LEGACY DUPLICATE ENQUEUE**

**Assessment**:
- ✓ EnqueueEventUseCase is USED (in Redis handler)
- ✓ Tests exist (46% coverage)
- ✗ Inconsistent error handling
- ✗ Some branches never executed

**Uncovered Branches**:
1. Input validation edge cases (Lines 80, 129, 178, 200-201)
2. UUID auto-generation fallback (Lines 235)
3. as_event_entity error paths (Lines 260-337)

**Why Low?**: Tests focus on happy path; missing validation error scenarios

**Impact**: Adding 5-6 unit tests → +15-20% coverage on this file

**Effort**: SMALL (1-2 hours)
- Add unit tests for validation failures
- Test empty/invalid input handling
- Test UUID fallback scenarios

---

### 📦 `app/infrastructure/processors/sync_processors.py` - **ERROR PATH GAPS (79%)**

```
Missing Coverage: Lines 88, 104, 109, 164-173, 213, 271, 320-339, 443
```

**Assessment**:
- ✓ Core processor implementations
- ✗ Error classification paths untested
- ✗ Exception handling branches missing

**Untested Scenarios**:
1. **ApiCallProcessor**: HTTP 5xx vs 4xx classification (Lines 88, 104, 109)
2. **Retry timeout handling** (Lines 164-173)
3. **gRPC error mapping** (Lines 271, 320-339)
4. **Callback metadata handling** (Lines 443)

**Why Low?**: Mock processors always succeed; missing error simulation tests

**Impact**: Adding 6-8 error scenario tests → +10-15% coverage

**Effort**: SMALL-MEDIUM (2-3 hours)
- Create mock HTTP responses (4xx, 5xx, timeout)
- Test error classification logic
- Test retry exhaustion behavior

---

## 3️⃣ FAILING TESTS - BLOCKERS FOR COVERAGE

### ❌ 12 Tests Failing (Preventing Coverage from Passing)

```
FAILED tests/unit/test_redis_handlers_unit.py (8 tests)
  - test_startup_connects_when_not_connected
  - test_startup_skips_connect_when_already_connected
  - test_subscriber_demo_ack_on_success
  - test_subscriber_demo_ack_on_exception
  - test_handle_processing_event_queue_ack_on_success
  - test_handle_processing_event_queue_nack_on_event_not_found
  - Plus 2 config tests

FAILED tests/functional/test_enqueue_event_concurrency_c1_c2.py (3 tests)
  - test_c1_concurrent_same_external_uuid
  - test_c2_concurrent_same_internal_id
  - test_c3_concurrent_mixed_id_and_external_uuid

FAILED tests/functional/test_savemany_event_repository_conflict.py (1 error)
  - save_or_resolve_one IntegrityError handling
```

**Root Causes**:
1. **Redis Handler Tests**: Mock patches fail (broker, session) → Skip actual execution
2. **Concurrency Tests**: save_or_resolve_one() fails on IntegrityError → Concurrent inserts
3. **Repository Test**: Race condition not fixed in save_or_resolve_one logic

**Impact**: 12 failing tests = ~50 untested statements + branch gaps

**Effort**: MEDIUM-HIGH (4-6 hours)
- Fix redis handler test mocks (patch correct targets)
- Fix save_or_resolve_one race condition (use merge logic)
- Add proper transaction isolation in functional tests

---

## 📈 TOP 5 OPPORTUNITIES (Prioritized)

### 🥇 **#1: Remove Dead Code (TRIVIAL)**

**What**: Delete `app/main.py` (1 statement)

**Why**: 
- Zero coverage, no usage
- Blocks coverage gate trivially

**Impact**: +0.08% coverage (1 statement)  
**Effort**: TRIVIAL (5 min)  
**Blocker**: None  
**Status**: Ready NOW

---

### 🥈 **#2: Fix Concurrency Tests (HIGH IMPACT)**

**What**: Fix `save_or_resolve_one` race condition in repository

**Why**:
- 3 FAILING tests (high impact on coverage)
- Blocks 50+ statements from being tested
- Root cause: IntegrityError on concurrent external_uuid conflicts

**Impact**: +4-5% coverage + fix production concurrency bug  
**Effort**: MEDIUM (3-4 hours)
- Analyze concurrency issue in detail
- Fix repository logic (use merge() or select-for-update)
- Verify tests pass

**Blocker**: Needs investigation first  
**Status**: NEXT (requires deep dive)

---

### 🥉 **#3: Add Redis Handler Tests (MEDIUM IMPACT)**

**What**: Create proper functional tests for Redis handlers

**Why**:
- 8 FAILING unit tests due to mock issues
- Missing 42 statements in critical handler code
- Tests need actual async/await + in-memory Redis

**Impact**: +8-10% coverage + remove FAILING tests  
**Effort**: MEDIUM (3-4 hours)
- Rewrite handler tests with proper FastStream mocks
- Use async test fixtures
- Test retry paths

**Blocker**: Needs FastStream testing patterns  
**Status**: MEDIUM priority

---

### 🏅 **#4: Add Processor Error Tests (QUICK WIN)**

**What**: Add error scenario tests to sync_processors.py

**Why**:
- Easy to add (mock responses)
- Covers critical error paths
- Blocks ~17 statements

**Impact**: +2-3% coverage  
**Effort**: SMALL (2 hours)
- Add mock HTTP error responses (4xx, 5xx)
- Test error classification
- Test timeout scenarios

**Blocker**: None  
**Status**: Ready NOW (after #1)

---

### 🏅 **#5: Remove Legacy ProcessEventUseCase (MAJOR CLEANUP)**

**What**: Delete ProcessEventUseCase (deprecated, 120 lines)

**Why**:
- Replaced by ProcessEventIdealUseCase
- Covers low-priority functionality
- Complex state machine logic with gaps
- Adds maintenance burden

**Impact**: +2-3% coverage + reduce complexity  
**Effort**: MEDIUM-HIGH (2-3 hours)
- Delete class + tests
- Clean up imports
- Verify no other uses

**Blocker**: Verify nothing else uses it  
**Status**: AFTER concurrency fix

---

## 🎯 RECOMMENDED EXECUTION ORDER

```
Day 1:
┌─────────────────────────────────────────┐
│ #1 Remove app/main.py (5 min)          │ ← QUICK WIN
│ #4 Add Processor Error Tests (2h)       │ ← MEDIUM IMPACT
│ Coverage: 82.61% → 84-85%               │
└─────────────────────────────────────────┘

Day 2 (Investigation):
┌─────────────────────────────────────────┐
│ #2 Deep dive: Analyze race condition    │ ← BLOCKER
│    in save_or_resolve_one()             │
│ Document root cause findings            │
└─────────────────────────────────────────┘

Day 3:
┌─────────────────────────────────────────┐
│ #2 Fix race condition (3-4h)            │ ← HIGH IMPACT
│ Run functional tests until green        │
│ Coverage: 84-85% → 88-90%               │
└─────────────────────────────────────────┘

Day 4:
┌─────────────────────────────────────────┐
│ #3 Rewrite Redis handler tests (3-4h)   │ ← CRITICAL
│ Use proper FastStream patterns          │
│ Coverage: 88-90% → 92-95%               │
└─────────────────────────────────────────┘

Bonus (if time):
┌─────────────────────────────────────────┐
│ #5 Remove legacy ProcessEventUseCase    │ ← CLEANUP
│    (2-3h)                               │
│ Coverage: 92-95% → 95%+                 │
└─────────────────────────────────────────┘
```

---

## ✅ Expected Outcomes

| Task | Current | Target | Gain |
|------|---------|--------|------|
| Overall Coverage | 82.61% | 95%+ | +12% |
| app/main.py | 0% | REMOVED | - |
| app/infrastructure/redis/main.py | 41% | 85%+ | +44% |
| app/core/usecases/event_usecases.py | 46% | 85%+ | +39% |
| Failing Tests | 12 ❌ | 0 ✅ | Fix ALL |
| Lines Coverage | 173 missing | < 80 missing | -93 lines |

---

## 🚨 Critical Findings

### Issue #1: Race Condition in save_or_resolve_one()

**Location**: `app/infrastructure/db/repository_event.py:170-220`

**Problem**:
```python
# Concurrent insert attempt
# Request 1: INSERT with external_uuid=X → SUCCESS
# Request 2: INSERT with external_uuid=X → INTEGRITY ERROR
# Then try to fetch: Query returns 0 rows (race!)
# Result: NoResultFound exception
```

**Why It's Critical**:
- Production bug: concurrent requests can fail
- Currently masked by catch + return Err
- Functional tests expose the issue (3 FAILING)

**Fix**: Use `session.merge()` or SELECT FOR UPDATE

---

### Issue #2: Redis Handler Tests Don't Actually Test Redis

**Location**: `tests/unit/test_redis_handlers_unit.py`

**Problem**:
```python
# Tests patch FastStream broker + UoW
# But never actually test:
#   - Message acknowledgment (msg.ack/nack)
#   - Retry logic timing
#   - Exception handling paths
#   - Publisher behavior
```

**Why It's Critical**:
- Handler is critical path in production
- 42 untested statements
- Error paths untested → silent failures possible

**Fix**: Use FastStream test utilities + in-memory broker

---

## 📝 Notes for Agentes IA

Use this document to:
1. **Identify quick wins** (#1, #4 can be done in < 4 hours)
2. **Understand blockers** (race condition must be fixed first)
3. **Plan sprints** (recommend 2-3 day effort for full coverage)
4. **Prioritize by impact** (concurrency fix > redis tests > cleanup)

All changes should:
- ✅ Maintain 85%+ coverage gate
- ✅ Pass ruff + mypy checks
- ✅ Include comprehensive tests
- ✅ Document architectural decisions

---

**Last Updated**: 2026-01-10  
**Status**: Analysis Complete - Ready for Implementation  
**Next Review**: After Day 1 quick wins
