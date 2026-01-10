# ✅ FIXED: ApiCallProcessor retries 4xx errors (PERMANENT)

**Fecha descubrimiento**: 2025-12-28  
**Fecha fix**: 2026-01-10  
**Severidad**: ALTA (Production Bug)  
**Estado**: ✅ RESUELTO

---

## 📋 Summary

El `ApiCallProcessor` actualmente **reintenta** errores HTTP 4xx (ej: 400, 404, 401) cuando NO debería hacerlo. Según la lógica de clasificación de errores:

- **4xx errors** = PERMANENT (errores de cliente/validación) → **NO reintentar**
- **5xx errors** = TRANSIENT (errores de servidor) → Reintentar

**Comportamiento esperado**: 1 intento, falla inmediatamente  
**Comportamiento actual**: 5 intentos (reintentos inútiles, aumenta latencia)

---

## 🔍 Root Cause

El `AsyncRetrying` de `tenacity` NO tiene configurado un filtro para excluir `ValueError` de los reintentos.

### Código actual (lines 124-134 sync_processors.py):

```python
async_retrying = AsyncRetrying(
    stop=stop_after_attempt(retry_config.max_attempts),  # ✅ Correcto
    wait=wait_exponential(
        multiplier=retry_config.backoff_multiplier,
        min=retry_config.initial_backoff,
        max=retry_config.max_backoff,
    ),
    reraise=True,  # ✅ Correcto
    # ❌ FALTA: retry=retry_if_not_exception_type(ValueError)
)
```

### Lógica de clasificación (lines 154-158):

```python
except httpx.HTTPStatusError as e:
    # 4xx errors are permanent, 5xx are transient
    if 400 <= e.response.status_code < 500:
        raise ValueError(f"HTTP {e.response.status_code}: {e}")  # Convierte a ValueError
    raise  # Preserva HTTPStatusError para 5xx
```

**Problema**: El `ValueError` lanzado por errores 4xx SÍ está siendo reintentado porque `AsyncRetrying` no tiene configurado qué excepciones EXCLUIR.

---

## 📊 Impact

### Performance

- **Latencia adicional**: 5 intentos para errores 4xx
  - Intento 1: 0ms
  - Intento 2: 100ms
  - Intento 3: 100ms
  - Intento 4: 500ms
  - Intento 5: 1000ms
  - **Total: +1700ms** de latencia innecesaria

### Production Scenarios

| Escenario                  | Error   | Intentos | Latencia Total | Correcto |
| -------------------------- | ------- | -------- | -------------- | -------- |
| **API con token inválido** | 401     | 5        | ~1700ms        | ❌       |
| **Recurso no existe**      | 404     | 5        | ~1700ms        | ❌       |
| **Request malformado**     | 400     | 5        | ~1700ms        | ❌       |
| **Rate limit alcanzado**   | 429     | 5        | ~1700ms        | ❌       |
| **Server error**           | 503     | 5        | ~1700ms        | ✅       |
| **Gateway timeout**        | 504     | 5        | ~1700ms        | ✅       |

### Cost Impact

- **APIs con rate limit**: Consumen 5x quota innecesariamente
- **APIs con metering**: Costo 5x por evento con error de cliente
- **Logs**: 5x volumne de error logs (ruido)

---

## 🧪 Test Evidence

El test `test_api_processor_http_400_permanent_error` documenta este comportamiento:

```python
@pytest.mark.asyncio
async def test_api_processor_http_400_permanent_error():
    """
    ⚠️ KNOWN BUG: Currently, the processor RETRIES ValueError exceptions
    (which are raised from 4xx errors). This is incorrect behavior - PERMANENT
    errors should NOT be retried.
    """
    # ... setup ...
    
    # Should raise ValueError (converted from 4xx)
    with pytest.raises(ValueError, match="HTTP 400"):
        await processor.process(event)
    
    # ⚠️ BUG: Currently retries 5 times (should be 1)
    assert mock_client.request.call_count == 5  # CURRENT (buggy) behavior
```

**Test location**: `tests/unit/test_sync_processors_error_unit.py`

---

## 🔧 Applied Fix

✅ **Option 1: Exclude ValueError from retries (IMPLEMENTED)**

**Changes made**:

1. **Import added** (line 19):
```python
from tenacity import retry_if_not_exception_type
```

2. **AsyncRetrying configuration updated** (lines 127-135):
```python
async_retrying = AsyncRetrying(
    stop=stop_after_attempt(retry_config.max_attempts),
    wait=wait_exponential(...),
    reraise=True,
    retry=retry_if_not_exception_type(ValueError),  # ✅ FIX: Don't retry ValueError
)
```

3. **Test updated** to validate correct behavior:
```python
assert mock_client.request.call_count == 1  # ✅ Validates 1 attempt only
```

**Validation**:
- ✅ All 11 error scenario tests passing
- ✅ All 26 existing processor tests passing
- ✅ No regressions detected

**Performance impact**:
- **Before**: 5 attempts × ~340ms = ~1700ms total latency for 4xx errors
- **After**: 1 attempt × ~0ms = ~0ms (immediate failure)
- **Improvement**: -1700ms per 4xx error ✨

---

## 🔧 Proposed Fix

### Option 1: Exclude ValueError from retries (Recommended)

```python
from tenacity import retry_if_not_exception_type

async_retrying = AsyncRetrying(
    stop=stop_after_attempt(retry_config.max_attempts),
    wait=wait_exponential(...),
    reraise=True,
    retry=retry_if_not_exception_type(ValueError),  # ✅ FIX: Don't retry ValueError
)
```

**Pros**:
- Simple, 1-line change
- Aligns with existing error classification logic
- No impact on TRANSIENT errors (5xx, timeouts, connection)

**Cons**:
- Si hay OTROS ValueError (no HTTP) que deberían reintentarse, necesitarían ajuste

### Option 2: Custom retry predicate

```python
def should_retry(exc: BaseException) -> bool:
    """Retry TRANSIENT errors only."""
    if isinstance(exc, ValueError):
        return False  # PERMANENT (validation, 4xx)
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True  # TRANSIENT
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500  # TRANSIENT only for 5xx
    return False  # Unknown = don't retry

async_retrying = AsyncRetrying(
    stop=stop_after_attempt(retry_config.max_attempts),
    wait=wait_exponential(...),
    reraise=True,
    retry=retry_if_result(should_retry),  # ✅ FIX: Custom predicate
)
```

**Pros**:
- Explícito, auto-documentado
- Flexible para agregar casos especiales

**Cons**:
- Más código, más complejo
- Duplica lógica de `classify_error()` method

---

## ✅ Recommended Action Plan (COMPLETED)

1. ✅ **Immediate** (Task #4B): Applied Option 1 fix
2. ✅ **Update test**: Changed `assert call_count == 5` → `assert call_count == 1`
3. ✅ **Validate**: Executed test suite, all tests passing
4. ✅ **Document**: Added comment in código explaining ValueError exclusion
5. ⏳ **Monitor**: After deploy, verify latency p95 improvement ~1700ms for 4xx errors

**Git Commit**: Task #4B complete - Production bug fixed

---

## 🎓 Lessons Learned

- **Test-driven debugging**: El test unitario reveló el bug ANTES de que afectara producción
- **Error classification**: Importante validar que configuración de retry RESPETA la clasificación
- **Documentation**: Bug documentado previene re-introducción en refactors

---

## 📚 References

- Tenacity docs: https://tenacity.readthedocs.io/en/latest/#custom-retrying
- Test file: `tests/unit/test_sync_processors_error_unit.py`
- Processor implementation: `app/infrastructure/processors/sync_processors.py` lines 120-180
- Related: `docs/RETRY_STRATEGY.md` (retry configuration)

---

**Owner**: Development Team  
**Created**: 2025-12-28  
**Updated**: 2025-12-28
