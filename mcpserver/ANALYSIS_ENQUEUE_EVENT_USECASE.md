## ANÁLISIS DE COBERTURA Y ESTRATEGIA PARA `EnqueueEventUseCase`

### 1. ANÁLISIS DE COBERTURA ACTUAL

✅ Tests actuales: 43 tests pasando

- Tests unitarios de repositorio de eventos
- Tests funcionales de repositorio de eventos
- Tests de validación y conflictos
- Tests de relaciones

❌ VACÍO: No hay tests específicos para `EnqueueEventUseCase`

- No hay test unitario con mocks de UoW
- No hay test de concurrencia funcional
- No hay test de idempotencia específico

---

### 2. ANÁLISIS DE `EnqueueEventUseCase`

#### Responsabilidades del UseCase:

```
1. VALIDACIONES PRE-SAVE:
   - Validar entrada con Pydantic (RootModel check)
   - Solo estados CREATED o None permitidos
   - Normalizar JSON fields (sort_keys=True)
   - Transición a PENDING state (solo si es nuevo)

2. IDEMPOTENCIA:
   - Por external_uuid primero
   - Por id segundo
   - Si existe: retornar evento existente sin cambios de estado
   - Si no existe: crear nuevo en estado PENDING

3. MANEJO DE ERRORES:
   - Constraint violations (unique): fallback a lookup
   - Validation errors: retornar ErrorDetail
   - Runtime errors: retornar ErrorDetail

4. TRANSACCIONALIDAD:
   - Usar UnitOfWork con SAVEPOINT
   - save_or_resolve() para idempotencia
   - Rollback automático en error
```

#### Flujo Principal:

```
Input → Validate Input → Check State → Normalize JSON →
Create Event → Transition to PENDING → save_or_resolve() →
On Error Check Unique → Lookup Existing → Return as_output
```

---

### 3. MATRIZ DE CASOS DE PRUEBA

#### 3.1 TESTS UNITARIOS (Con Mocks)

Objetivo: Validar lógica sin BD, usando inyección de dependencias

| Caso   | Descripción                                   | Mock Needed                 | Expected Result                   |
| ------ | --------------------------------------------- | --------------------------- | --------------------------------- |
| **U1** | Input válido, nuevo evento                    | UoW mock save_or_resolve ok | Ok(output) en PENDING             |
| **U2** | Input inválido (Pydantic)                     | -                           | Err(VALIDATION_FAILED)            |
| **U3** | Estado inválido (no CREATED)                  | -                           | Err(VALIDATION_FAILED)            |
| **U4** | Normalización JSON                            | -                           | JSON ordenado deterministicamente |
| **U5** | Transición válida (CREATED→PENDING)           | -                           | Ok(event) en PENDING              |
| **U6** | Constraint violation, lookup by external_uuid | UoW mock + exception        | Ok(existing_event)                |
| **U7** | Constraint violation, fallback lookup by id   | UoW mock + exception        | Ok(existing_event)                |
| **U8** | Constraint violation, no existente            | UoW mock + exception        | Err(detail)                       |

#### 3.2 TESTS FUNCIONALES (Sin Mocks, BD en Memoria)

Objetivo: Validar integración real con BD

| Caso   | Descripción                         | Setup BD         | Expected Result           |
| ------ | ----------------------------------- | ---------------- | ------------------------- |
| **F1** | Enqueue nuevo evento                | BD vacía         | Ok(event) PENDING + en BD |
| **F2** | Enqueue con external_uuid duplicado | Evento existente | Ok(existing) mismo estado |
| **F3** | Enqueue con id duplicado            | Evento existente | Ok(existing) mismo estado |
| **F4** | Payload JSON con dicts anidados     | BD vacía         | JSON normalizado          |
| **F5** | Context JSON vacío vs None          | BD vacía         | Ambos normalizados a {}   |

#### 3.3 TESTS DE CONCURRENCIA (Funcionales)

Objetivo: Validar idempotencia ante requests simultáneos

| Caso   | Descripción                        | Concurrency    | Expected Result                  |
| ------ | ---------------------------------- | -------------- | -------------------------------- |
| **C1** | 2 requests con mismo external_uuid | asyncio.gather | Ambos retornan mismo evento      |
| **C2** | 5 requests con mismo id            | asyncio.gather | Ambos retornan mismo evento      |
| **C3** | Request mixed (external_uuid + id) | asyncio.gather | Uno gana, otro retorna existente |

---

### 4. ESTADO DE GUIDELINES EN Agents.md

#### Sección: "Testing por Capas" (✅ Existe pero incompleta)

- Menciona Unit vs Functional
- NO detalla inyección de dependencias
- NO explica cómo estructurar mocks para UseCase
- NO define fixtures necesarias

#### Sección: "Ejemplo correcto en tests" (❌ Solo para Repository)

- Ejemplo es para AsyncSQLAlchemyEventRepository
- NO hay ejemplo para UseCase
- NO hay ejemplo de UoW mock

#### Recomendación:

📝 **ACTUALIZAR Agents.md** con:

1. Sección "Testing Use Cases" con inyección de dependencias
2. Fixture factory para UoW mocks
3. Ejemplo de UseCase con mock UoW
4. Patrón de prueba para idempotencia

---

### 5. ESTRATEGIAS DISPONIBLES

#### ESTRATEGIA A: "Foundation First" (Recomendada)

1. ✅ Actualizar Agents.md con guidelines de testing UseCase
2. ✅ Crear fixtures para mocks de UoW
3. ✅ Implementar tests unitarios (U1-U8)
4. ✅ Implementar tests funcionales (F1-F5)
5. ✅ Implementar tests de concurrencia (C1-C3)

**Ventaja**: Código bien documentado desde inicio
**Tiempo**: 4-5 horas

#### ESTRATEGIA B: "Quick Coverage"

1. ✅ Tests unitarios (U1-U8) sin actualizar docs
2. ✅ Tests funcionales (F1-F5)
3. ✅ Tests concurrencia (C1-C3)
4. 📝 Documentar en Agents.md después

**Ventaja**: Tests listos primero, docs después
**Tiempo**: 3-4 horas

#### ESTRATEGIA C: "Iterativo"

1. ✅ Actualizar Agents.md con section "Testing Use Cases"
2. ✅ Tests unitarios (U1-U5) - validación y lógica básica
3. ✅ Tests funcionales (F1-F3) - happy path
4. ✅ Expandir a más casos (U6-U8, F4-F5)
5. ✅ Tests de concurrencia (C1-C3)

**Ventaja**: Feedback temprano, iteración flexible
**Tiempo**: 5-6 horas con pasos intermedios

---

### 6. RECOMENDACIÓN

**Sugiero ESTRATEGIA A + C** (híbrida):

✅ **Fase 1** (30-40 min):

- Actualizar Agents.md con guidelines
- Crear fixtures de UoW mock

✅ **Fase 2** (1.5-2 h):

- Tests unitarios U1-U5 (validación, normalización, transición)
- Obtener feedback

✅ **Fase 3** (1.5-2 h):

- Tests unitarios U6-U8 (error handling)
- Tests funcionales F1-F3

✅ **Fase 4** (1-1.5 h):

- Tests funcionales F4-F5
- Tests de concurrencia C1-C3

---

### 7. PRIORIDADES SUGERIDAS

🔴 **CRÍTICO** (cubre 80% de valor):

- Tests unitarios U1-U5 (core logic)
- Tests funcionales F1-F3 (happy path + idempotencia)
- Tests concurrencia C1-C2 (race conditions)

🟡 **IMPORTANTE** (cubre 15% de valor):

- Tests unitarios U6-U8 (error handling edge cases)
- Test funcional F4-F5 (JSON normalization)
- Test concurrencia C3 (mixed scenarios)

🟢 **NICE-TO-HAVE**:

- Documentación en Agents.md (aunque recomendado)
- Benchmarks de performance

---

Ahora puedes elegir:

1. ¿Qué estrategia prefieres? (A, B, C, o híbrida)
2. ¿Por cuál paso empezamos primero?
