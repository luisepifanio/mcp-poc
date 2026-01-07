# Agent Iteration Guide

Este documento complementa `Agents.md` con un workflow recomendado para iteraciones rápidas entre un desarrollador humano y un agente IA, además de un breve análisis de la interacción reciente.

## Resumen de cambios recientes

- Helper `async_chain` añadido para componer etapas async que retornan `Result`.
- `ProcessEventIdealUseCase` implementado con 4 fases: `validate_and_lock` (TX1), `process_with_retries`, `persist_outcome` (TX2), y `execute`.
- Test funcional E2E para validar TX1/TX2: `tests/functional/test_process_event_tx_transactions.py`.
- `saveMany` corregido en `app/infrastructure/db/repository_event.py` para `merge()` de instancias detachadas antes de `add()` evitando `IntegrityError` en E2E.

## Workflow recomendado por iteración

1. Definir en 3-5 líneas el objetivo y los criterios de aceptación (incluir IDs de tests que deben pasar).
2. Diseñar la API/contrato del core (UseCase/Entity) y listar los escenarios críticos.
3. Implementar el core y escribir tests unitarios que cubran rutas felices y errores esperados.
4. Ejecutar los tests unitarios del módulo y arreglar fallos antes de avanzar.
5. Añadir 1 test funcional crítico (E2E) que valide transacciones o idempotencia.
6. Ejecutar la suite completa y revisar cobertura; priorizar tests para módulos con coverage bajo.
7. Actualizar documentación breve (Agents.md o docs/) con: cambios de diseño, puntos de riesgo y comandos para reproducir.

## Lista de verificación (quick)

- [ ] Objetivo y criterios definidos
- [ ] Core implementado + unit tests
- [ ] Unit tests verdes
- [ ] E2E crítico agregado
- [ ] Suite completa verde y cobertura aceptable
- [ ] Documentación actualizada

## Prácticas operativas concretas

- Tests E2E con BD: siempre leer la fila canónica antes de pasar una entidad a un UseCase que hará un `save` para evitar conflictos por objetos detachados.
- Para insertar idempotentemente en tests, preferir `save_or_resolve_one` o `save_or_resolve`.
- Cuando el UseCase hace `TX1` (guardar lock), el processor que verifica la persistencia debe usar una sesión separada (simula consumidor externo).
- Hacer commits pequeños y frecuentes; mantener cambios ciclo corto (implementación → tests → corrección → commit).

## Comunicación entre humano y agente

- El humano define: objetivo, criterios de aceptación y restricciones (p. ej. no tocar infra).
- El agente propone plan (TODO list), implementa cambios pequeños y ejecuta tests específicos.
- Antes de modificar múltiples archivos, el agente debe pedir confirmación para cambios de alto impacto (DB, contratos públicos).

## Ejemplo de comandos locales sugeridos

```bash
# ejecutar tests del módulo modificado
uv run pytest tests/unit/test_process_event_ideal_validate_lock.py -q

# ejecutar test funcional específico
uv run pytest tests/functional/test_process_event_tx_transactions.py -q -k tx1

# ejecutar suite completa y generar reporte de cobertura
uv run pytest --cov=app --cov-report=html
```

---

Fecha: 2026-01-06
