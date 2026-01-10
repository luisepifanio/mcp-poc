# 🎯 ACTIONABLE TODO: Top 5 Improvement Opportunities

**Status**: Analysis Complete  
**Recommendation**: NOT YET PRODUCTION READY (82.61% coverage < 85% gate)  
**Timeline**: 4 phases, ~16 hours total

---

## PHASE 1: QUICK WINS (Today - 4 hours)

### Task #1: Remove Dead Code [5 MIN]

**File**: `app/main.py`  
**Action**:

```bash
# 1. Delete the file
rm app/main.py

# 2. Verify no imports remain
grep -r "from app.main" app/ tests/ || echo "✅ No imports"

# 3. Run tests
uv run pytest -q

# Expected: Coverage 82.61% → 82.69% (+0.08%)
```

**Effort**: TRIVIAL (5 min)  
**Impact**: +0.08% coverage  
**Risk**: NONE

---

### Task #4: Add Processor Error Tests [2 HOURS]

**File**: `tests/unit/test_sync_processors_error_unit.py` (NEW)  
**Actions**:

```bash
# 1. Create new test file with error scenarios:
#    - ApiCallProcessor: HTTP 4xx (PERMANENT)
#    - ApiCallProcessor: HTTP 5xx (TRANSIENT)
#    - ApiCallProcessor: Timeout (TRANSIENT)
#    - GrpcProcessor: Error classification
#    - Retry exhaustion
#    - Callback metadata

# 2. Example test structure:
cat > tests/unit/test_sync_processors_error_unit.py << 'EOF'
import pytest
from app.infrastructure.processors.sync_processors import ApiCallProcessor
from app.core.processors import ErrorType

@pytest.mark.asyncio
async def test_api_processor_http_400_permanent():
    """HTTP 4xx = PERMANENT (no retry)"""
    # TODO: Implement
    pass

@pytest.mark.asyncio
async def test_api_processor_http_503_transient():
    """HTTP 5xx = TRANSIENT (retry)"""
    # TODO: Implement
    pass

# ... more tests
EOF

# 3. Run tests
uv run pytest tests/unit/test_sync_processors_error_unit.py -v

# 4. Expected: +2-3% coverage on sync_processors.py
#    Coverage: 82.69% → 84-85%
```

**Effort**: SMALL (2 hours)  
**Impact**: +2-3% coverage  
**Risk**: NONE (new tests only)

---

## PHASE 2: INVESTIGATION & CRITICAL FIX (Tomorrow - 4-5 hours)

### Task #2: Fix Race Condition [3-4 HOURS]

**File**: `app/infrastructure/db/repository_event.py` (lines 170-220)  
**Problem**: Concurrent requests with same external_uuid cause NoResultFound  
**Tests Failing**:

- test_c1_concurrent_same_external_uuid
- test_c2_concurrent_same_internal_id
- test_c3_concurrent_mixed_id_and_external_uuid

**Investigation Steps**:

```bash
# 1. Run failing tests to see exact error
uv run pytest tests/functional/test_enqueue_event_concurrency_c1_c2.py -v

# 2. Read the error logs carefully
#    Look for: IntegrityError → NoResultFound flow

# 3. Understand SQLAlchemy async session semantics:
#    - When does flush() make changes visible?
#    - When do other sessions see committed changes?
#    - What is session.merge() behavior?

# 4. Design solution:
#    Option A: Use session.merge() (RECOMMENDED)
#    Option B: Use SELECT FOR UPDATE
#    Option C: Nested transactions/savepoints
```

**Implementation** (Option A - Recommended):

```python
# In save_or_resolve_one():
try:
    await self.session.flush()
except IntegrityError:
    # Collision detected; resolve by finding existing
    await self.session.rollback()

    # Query both ID and external_uuid
    stmt = select(Event).where(
        (Event.id == event.id) |
        (Event.external_uuid == event.external_uuid)
    )
    result = await self.session.execute(stmt)
    existing = result.scalars().first()

    if existing:
        # Merge existing instance
        merged = await self.session.merge(existing)
        return Ok([merged])

    # If no existing found, this is unexpected
    raise  # Re-raise IntegrityError
```

**Verification**:

```bash
# 1. Run failing tests
uv run pytest tests/functional/test_enqueue_event_concurrency_c1_c2.py::test_c1_concurrent_same_external_uuid -v

# 2. All 3 concurrency tests should PASS
uv run pytest tests/functional/test_enqueue_event_concurrency_c1_c2.py -v

# 3. Full suite should pass
uv run pytest -q

# 4. Check coverage (should improve significantly)
uv run pytest --cov=app --cov-fail-under=85 -q

# Expected: Coverage 84-85% → 88-90%
```

**Effort**: MEDIUM (3-4 hours)  
**Impact**: +4-5% coverage + PRODUCTION BUG FIX  
**Risk**: LOW (isolated change, well-tested)  
**Blocker**: NONE (but blocks #3, #5)

---

## PHASE 3: CRITICAL PATH TESTING (Day 3 - 3-4 hours)

### Task #3: Rewrite Redis Handler Tests [3-4 HOURS]

**Files**:

- `tests/unit/test_redis_handlers_unit.py` (FIX 8 FAILING TESTS)
- `tests/unit/test_redis_config_unit.py` (FIX 2 FAILING TESTS)

**Current Issue**: Tests mock dependencies but don't test actual behavior

**Solution**: Use FastStream test utilities

```bash
# 1. Learn FastStream testing patterns:
#    - TestBroker context manager
#    - Async message publishing
#    - Message acknowledgment testing

# 2. Rewrite test_startup_connects_when_not_connected:
cat > tests/unit/test_redis_handlers_unit.py << 'EOF'
from faststream.testing import TestBroker

@pytest.mark.asyncio
async def test_startup_connects_when_not_connected():
    """Test broker connects on startup"""
    # Use actual TestBroker instead of mocks
    async with TestBroker() as broker:
        # Verify connection established
        assert broker._connection is not None
        # etc...
EOF

# 3. Fix all 8 FAILING tests in redis_handlers_unit.py

# 4. Fix 2 FAILING tests in redis_config_unit.py
#    - test_broker_imports_successfully
#    - test_settings_integration_with_redis_module

# 5. Run all tests
uv run pytest tests/unit/test_redis_handlers_unit.py -v
uv run pytest tests/unit/test_redis_config_unit.py -v

# Expected: ALL 10 TESTS PASSING ✅
#          Coverage: 88-90% → 92-95%
```

**Effort**: MEDIUM (3-4 hours)  
**Impact**: +8-10% coverage + FIX 10 FAILING TESTS  
**Risk**: LOW (replacing broken tests)  
**Blocker**: Depends on #2 being fixed

---

## PHASE 4: CLEANUP (Optional Day 4 - 2-3 hours)

### Task #5: Remove Legacy ProcessEventUseCase [2-3 HOURS]

**File**: `app/core/usecases/event_usecases.py` (lines 215-337)  
**Actions**:

```bash
# 1. Verify no other code uses ProcessEventUseCase:
grep -r "ProcessEventUseCase" app/ tests/ docs/ --exclude="*.pyc"
# Should only find class definition + tests for it

# 2. Check that ProcessEventIdealUseCase is used instead:
grep -r "ProcessEventIdealUseCase" app/
# Should find references in Redis handler + tests

# 3. Delete the class (lines 215-337)
#    - Remove class definition
#    - Remove helper methods specific to it
#    - Remove docstrings

# 4. Delete associated tests:
rm tests/unit/test_process_event_usecase*
rm tests/functional/test_process_event_usecase2*

# 5. Clean up imports:
uv run ruff check --fix .
uv run ruff format .

# 6. Run full suite:
uv run pytest -q

# Expected: Coverage 92-95% → 95%+ ✨
#           All 255 tests PASSING ✅
```

**Effort**: MEDIUM (2-3 hours)  
**Impact**: +2-3% coverage + REDUCE TECH DEBT  
**Risk**: LOW (isolated deletion)  
**Blocker**: Depends on #2

---

## 🚀 EXECUTION CHECKLIST

### BEFORE Starting

- [ ] Read `docs/TOP_5_OPPORTUNITIES_DECISION_MATRIX.md`
- [ ] Understand all 5 opportunities
- [ ] Review current coverage report

### PHASE 1 (Today)

- [ ] Task #1: Delete app/main.py
- [ ] Verify no imports remain
- [ ] Task #4: Create new error tests file
- [ ] Add 6-8 error scenario tests
- [ ] Run full suite: `uv run pytest -q`
- [ ] Check coverage (target: 84-85%)
- [ ] Commit: `git add -A && git commit -m "test: add processor error scenarios + cleanup dead code"`

### PHASE 2 (Tomorrow)

- [ ] Read failing test logs in detail
- [ ] Understand race condition root cause
- [ ] Design solution (merge vs SELECT FOR UPDATE)
- [ ] Implement fix in save_or_resolve_one()
- [ ] Run concurrency tests: `uv run pytest tests/functional/test_enqueue_event_concurrency_c1_c2.py -v`
- [ ] Run full suite: `uv run pytest -q`
- [ ] Check coverage (target: 88-90%)
- [ ] Commit: `git add -A && git commit -m "fix: resolve race condition in save_or_resolve_one using merge pattern"`

### PHASE 3 (Day 3)

- [ ] Learn FastStream test patterns
- [ ] Rewrite test_redis_handlers_unit.py (8 tests)
- [ ] Rewrite test_redis_config_unit.py (2 tests)
- [ ] Run all tests: `uv run pytest tests/unit/ -v`
- [ ] Run full suite: `uv run pytest -q`
- [ ] Check coverage (target: 92-95% ✅ GATE PASSED)
- [ ] Commit: `git add -A && git commit -m "test: rewrite redis handler tests with faststream patterns"`

### PHASE 4 (Optional Day 4)

- [ ] Verify ProcessEventUseCase not used elsewhere
- [ ] Delete legacy class + tests
- [ ] Clean up imports
- [ ] Run full suite: `uv run pytest -q`
- [ ] Check coverage (target: 95%+)
- [ ] Commit: `git add -A && git commit -m "refactor: remove deprecated processevenusecase"`

### FINAL VERIFICATION

Before pushing to production:

- [ ] All 255 tests PASSING
- [ ] Coverage >= 95%
- [ ] `uv run ruff check .` PASS
- [ ] `uv run mypy app` PASS
- [ ] No warnings in logs
- [ ] Race condition verified fixed
- [ ] Production code quality verified

---

## 📊 SUCCESS METRICS

| Metric           | Current | After Phase 1 | After Phase 3 | After Phase 4 |
| ---------------- | ------- | ------------- | ------------- | ------------- |
| Coverage         | 82.61%  | 84-85%        | 92-95% ✅     | 95%+ ✨       |
| Tests Passing    | 236     | 244+          | 252+          | 255 ✅        |
| Tests Failing    | 12      | 4-6           | 0 ✅          | 0 ✅          |
| Dead Code Lines  | ~100    | ~100          | ~100          | ~0 🧹         |
| Production Ready | ❌      | ⚠️            | ✅            | ✅✨          |

---

## 📝 GIT COMMIT MESSAGES

```bash
# Phase 1
git commit -m "test(processors): add error scenario unit tests

- Add HTTP 4xx vs 5xx error classification tests
- Add timeout handling tests
- Add retry exhaustion tests
- Add callback metadata handling tests
- Coverage: app/infrastructure/processors/sync_processors.py 79% → 85%+

Tests: +6-8 new tests
Coverage: +2-3%"

# Phase 2
git commit -m "fix(repository): resolve race condition in save_or_resolve_one

Fix concurrent INSERT conflicts in external_uuid deduplication:
- Use session.merge() instead of simple SELECT on conflict
- Prevents NoResultFound when concurrent requests with same external_uuid
- Ensures idempotence guarantee

Fixes:
- test_c1_concurrent_same_external_uuid
- test_c2_concurrent_same_internal_id
- test_c3_concurrent_mixed_id_and_external_uuid

Coverage: +4-5%"

# Phase 3
git commit -m "test(redis): rewrite handler tests with faststream patterns

Rewrite unit tests to use FastStream TestBroker:
- Fix mock patches (use correct targets)
- Test actual async/await paths
- Test message acknowledgment
- Test error scenarios and retries

Fixes 10 FAILING tests:
- test_startup_connects_when_not_connected
- test_startup_skips_connect_when_already_connected
- test_subscriber_demo_ack_on_success
- test_subscriber_demo_ack_on_exception
- test_handle_processing_event_queue_ack_on_success
- test_handle_processing_event_queue_nack_on_event_not_found
- Plus 4 more config tests

Coverage: +8-10%"

# Phase 4
git commit -m "refactor(usecases): remove deprecated ProcessEventUseCase

Remove ProcessEventUseCase (deprecated, replaced by ProcessEventIdealUseCase):
- Delete class definition (120 lines)
- Delete associated tests
- Delete transition_event helper (not used elsewhere)
- Reduce technical debt

ProcessEventIdealUseCase is the canonical implementation.

Coverage: +2-3%"
```

---

## ⚠️ CRITICAL NOTES

1. **Phase 2 must be done before Phase 3** - Can't properly test Redis handlers until race condition is fixed
2. **All phases must pass `uv run pytest -q`** - Don't proceed if tests fail
3. **Quality gates must pass before commit**:

   ```bash
   uv run ruff check .      # Must PASS
   uv run mypy app          # Must PASS (strict mode)
   uv run pytest --cov=app --cov-fail-under=85  # Must pass coverage
   ```

4. **No commits to master/main** - Use feature branch and create PR

---

## 📞 REFERENCE DOCUMENTS

See also:

- `docs/COVERAGE_ANALYSIS_OPPORTUNITIES.md` - Detailed analysis
- `docs/TOP_5_OPPORTUNITIES_DECISION_MATRIX.md` - Complete decision matrix
- `Agents.md` - Development workflow and patterns

---

**Status**: READY FOR IMPLEMENTATION  
**Last Updated**: 2026-01-10  
**Next Action**: Approve plan and start Phase 1
