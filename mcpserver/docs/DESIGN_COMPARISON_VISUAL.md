# Comparativa Visual: Diseños de UseCase + Handler

## 🔴 Patrón ACTUAL (Problemático)

```
┌─────────────────────────────────────────────────────────────┐
│ Handler (redis/main.py)                                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  @EnqueueEventSubscriber                                      │
│  async def handle_enqueue_event(..., session=Depends(...)):  │
│                                                               │
│      uow = AsyncSQLAlchemyUnitOfWork(session)  ← NO context  │
│      usecase = EnqueueEventUseCase(uow)                       │
│      result = await usecase.execute(event)     ← Sin orquesta │
│                                                               │
│      # ❌ PROBLEMA: publish aquí, pero evento ya commiteado  │
│      if result.is_ok():                                       │
│          # await broker.publish(...)  ← NO ATÓMICO           │
│          await msg.ack()                                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         │
         └─────────────┬──────────────────┐
                       │                  │
         ┌─────────────▼──────────┐      │
         │ UseCase                │      │
         ├────────────────────────┤      │
         │ async def execute(...) │      │
         │   async with self.uow: │ ← ABRE
         │     evt = Event(...)   │      │
         │     save(evt)          │      │
         │   # CIERRA aquí        │ ← CIERRA
         │     COMMIT + close     │
         │                        │
         └────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │ UnitOfWork              │
         ├─────────────────────────┤
         │ __aenter__: init repos  │
         │ __aexit__:              │
         │   - commit()            │
         │   - close() session     │
         └─────────────────────────┘

Flujo de Transacción:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UseCase abre:     ▬▬▬▬▬ (TX1)
                   ├─ save evento
                   └─ COMMIT ✓
Sesión cerrada:    ▬▬▬
Publishing aquí:   ❌ Fuera de transacción
Otro UseCase:      ▬▬▬▬▬ (TX2) ← Separada!
```

---

## 🟢 Patrón PROPUESTO (Alternativa A)

```
┌──────────────────────────────────────────────────────────────┐
│ Handler (redis/main.py)  ← ORQUESTA TRANSACCIÓN              │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  @EnqueueEventSubscriber                                       │
│  async def handle_enqueue_event(..., session=Depends(...)):   │
│                                                                │
│      ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ TRANSACTION ABIERTA ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬│
│      │                                            │           │
│      │  async with AsyncSQLAlchemyUnitOfWork(...) as uow: │
│      │      # 1. UseCase (sin context manager)  │           │
│      │      usecase = EnqueueEventUseCase(uow)  │           │
│      │      result = await usecase.execute(...) │           │
│      │      # ✅ DENTRO TRANSACCIÓN             │           │
│      │                                            │           │
│      │      # 2. Publicar (dentro transacción)  │           │
│      │      if result.is_ok():                   │           │
│      │          await broker.publish(...)        │           │
│      │          # ✅ Si falla → ROLLBACK         │           │
│      │          await msg.ack()                  │           │
│      │      else:                                 │           │
│      │          await msg.nack()                 │           │
│      │  # COMMIT automático en __aexit__        │           │
│      ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
│                                                                │
└──────────────────────────────────────────────────────────────┘
         │                          │
         │                          │
    ┌────▼─────────────┐      ┌─────▼──────────────┐
    │ UseCase1         │      │ UseCase2 (future)  │
    ├──────────────────┤      ├────────────────────┤
    │ async def        │      │ async def execute..│
    │  execute(...):   │      │   (NO context mgr) │
    │  # SIN async with│ ✓    │                    │
    │  evt = Event(..)│      │ Usa mismo UoW      │
    │  save(evt)      │      │                    │
    │  return result  │      │                    │
    │  # NO CIERRA    │      │                    │
    │                 │      │                    │
    └─────────────────┘      └────────────────────┘
         ▲                            ▲
         │                            │
         └────────────┬───────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │ UnitOfWork (Shared)     │
         ├─────────────────────────┤
         │ __aenter__: init repos  │
         │ __aexit__:              │
         │   - commit() (una vez)  │
         │   - close() (una vez)   │
         │                         │
         │ ✅ Mantiene estado      │
         │ ✅ Múltiples ops atóm.  │
         └─────────────────────────┘

Flujo de Transacción:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Handler abre:      ▬▬▬▬▬▬▬▬▬▬▬▬▬▬ (TX1)
  ├─ UseCase1.execute()
  │  ├─ save evento
  │  └─ (sin commit)
  │
  ├─ Publishing
  │  └─ (sin commit, dentro TX)
  │
  └─ COMMIT al salir ✓ ← ATÓMICO
```

---

## 📊 Composición de Use Cases

### ❌ Actual (No composable)

```
Test: Ejecutar 2 use cases

async def test_multiple_usecases():
    uow = create_uow()
    
    uc1 = UseCase1(uow)
    result1 = await uc1.execute(input1)
    # UseCase1 abre: TX1
    #               ├─ save
    #               └─ COMMIT ✓
    
    uc2 = UseCase2(uow)
    result2 = await uc2.execute(input2)
    # UseCase2 abre: TX2 ← NUEVA TRANSACCIÓN
    #               ├─ update
    #               └─ COMMIT ✓
    
    # ❌ PROBLEMA: Transacciones separadas
    # ❌ No hay rollback coordinado
    # ❌ No puedes testar atomicidad
```

---

### ✅ Propuesto (Composable)

```
Test: Ejecutar 2 use cases con atomicidad

async def test_multiple_usecases():
    async with uow_factory() as uow:  # ← 1 transacción
        
        uc1 = UseCase1(uow)
        result1 = await uc1.execute(input1)
        # Dentro UoW:
        # ├─ save evento
        # └─ (sin commit)
        
        uc2 = UseCase2(uow)
        result2 = await uc2.execute(input2)
        # Dentro MISMO UoW:
        # ├─ update estado
        # └─ (sin commit)
        
        # Ambos committed juntos al salir
        
        # ✅ VENTAJA: Atomicidad garantizada
        # ✅ Si uc2 falla → rollback de uc1 también
        # ✅ Transacción única coordinada
```

---

## 🔄 Comparación Detallada

```
Criterio                  │ ACTUAL          │ PROPUESTO
──────────────────────────┼─────────────────┼──────────────────
Abre transacción          │ UseCase         │ Handler
Composable 2+ use cases   │ ❌ No           │ ✅ Sí
Enqueue + Publish atómico │ ❌ No           │ ✅ Sí
Cierra transacción        │ UseCase         │ Handler
Testeable en composición  │ ❌ No           │ ✅ Sí
Responsabilidad clara     │ ⚠️  Confusa     │ ✅ Clara
SRP (SOLID)              │ ❌ UseCase hace  │ ✅ Separación
                          │    mucho        │    clara
```

---

## 🏗️ Diagrama Secuencial Actual

```
Handler              UseCase              UoW               BD
   │                   │                  │                │
   ├─ crear UoW ──────────────────────────┼────────────────┤
   │                   │                  │                │
   ├─ execute ────────>│ async with UoW:  │                │
   │                   ├─────────────────>│ __aenter__      │
   │                   │                  │────────────────>│
   │                   │                  │ conexión        │
   │                   │                  │<────────────────│
   │                   │                  │                │
   │                   │  crear Event     │                │
   │                   │  save_or_resolve─┼───────────────>│
   │                   │                  │    INSERT      │
   │                   │                  │<───────────────│
   │                   │                  │ COMMIT         │
   │                   │                  │────────────────>│
   │                   │<─ return Result  │                │
   │<─ return ─────────┤                  │ close()        │
   │                   │                  │────────────────>│
   │                   │                  │                │
   │ ❌ publish aquí   │                  │ sesión cerrada  │
   │ (fuera TX)        │                  │                │
```

---

## 🏗️ Diagrama Secuencial Propuesto

```
Handler              UseCase              UoW               BD
   │                   │                  │                │
   │ async with UoW:   │                  │                │
   ├──────────────────────────────────────>│ __aenter__      │
   │                  │                  │────────────────>│
   │                  │                  │ conexión        │
   │                  │                  │<────────────────│
   │                  │                  │                │
   │ execute ────────>│ crear Event      │                │
   │                 │ save_or_resolve──┼───────────────>│
   │                 │                  │    INSERT      │
   │                 │                  │<───────────────│
   │                 │<─ Result         │                │
   │<─ Result ──────┘                   │                │
   │                                    │                │
   │ publish ──────────────────────────────────────────>│
   │ (dentro TX)                        │                │
   │                                    │                │
   │ salir: __aexit__ ─────────────────>│ COMMIT         │
   │                                    │────────────────>│
   │                                    │<───────────────│
   │                                    │ close()        │
   │                                    │────────────────>│
   ✓ ATÓMICO: save + publish en 1 TX
```

---

## 🎯 Decisión Final

**Recomendación**: **ALTERNATIVA A** - UseCase sin context manager

### Justificación

1. **Clarity**: 
   - Handler = Orquestación y transacción
   - UseCase = Lógica de negocio pura

2. **Atomicity**:
   - Enqueue + Publish en 1 transacción
   - Rollback coordinado

3. **Composability**:
   - Múltiples use cases en 1 transacción
   - Tests pueden componer con facilidad

4. **Testability**:
   - UseCase tests no necesitan transacción
   - Handler tests comprueban orquestación

5. **SOLID**:
   - SRP: Cada cosa su responsabilidad
   - OCP: Fácil agregar nuevos use cases
   - DIP: UseCase depende de UoW interface

---

## 📋 Plan de Refactorización

### Fase 1: Cambiar EnqueueEventUseCase
```python
# QUITAR: async with self.uow:
# MANTENER: Lógica interna
# ASUMIR: Transacción ya abierta por caller
```

### Fase 2: Actualizar handle_enqueue_event
```python
# AGREGAR: async with AsyncSQLAlchemyUnitOfWork(...)
# ORQUESTAR: UseCase + Publishing
# GARANTIZAR: Atomicidad
```

### Fase 3: Refactorizar Tests
```python
# Unit tests: UseCase sin transacción
# Functional tests: Handler con transacción
# Integration tests: Composición de use cases
```

### Fase 4: Extender a otros Use Cases
```python
# ProcessEventUseCase
# TransitionEventUseCase
# (Todos sin context manager)
```
