# Roadmap de Exploración y Evolución

Este documento guía el trabajo próximo en el codebase para estabilidad, nuevas features y preparación de infraestructura.

## 1. Oportunidades de mejora en el codebase

- Tipado estricto (mypy) en módulos: `scrapy_spider/*`, `redis/main.py`, `api/main.py`.
- Limpieza de `type: ignore` innecesarios.
- Revisión de `repository_event.py`: simplificar selects y loaders; documentar relaciones.
- Unificar patrones de Result[T, E] en todos los use cases.
- Reducir warnings de pytest marks no registradas (e.g. `@pytest.mark.redis`).

## 2. Dejar un codebase estable

- Quality gates obligatorios: `ruff` + `mypy` + `pytest` pasan localmente.
- Congelar API pública; cambios solo con tests y docs.
- Agregar `pre-commit` con hooks: ruff, mypy y pytest (rápido / `-k smoke`).

## 3. Ingeniería de requerimientos (fase event processing)

- Documentar estados y transiciones: CREATED → PENDING → PROCESSING → COMPLETED/FAILED.
- Definir SLA/errores temporales y política de reintentos.
- Especificar DTOs de entrada/salida por tipo de evento.
- Aceptación: tests funcionales para cada flujo + concurrencia.

## 4. Diseño: procesar eventos por nombre vs delegar gRPC

- Opción A (local): registro de handlers por `event.name`, orquestado vía UseCase.
- Opción B (delegado): enrutamiento a nodos externos vía gRPC; workers especializados.
- Criterios de decisión: latencia, aislamiento de fallas, elasticidad, complejidad operativa.
- POC: implementar ambos en pequeño, comparar.

## 5. Tilt Dev (IaC para entorno local)

- Objetivo: levantar `api`, `db`, `redis`, `workers` con live reload.
- Archivos: `Tiltfile` + `tilt_configs/*`.
- Integración: scripts `uv` dentro de Tilt; health checks; logs centralizados.

## 6. Transición a monorepo formal

- Estructura propuesta: `apps/` (api, workers), `libs/` (shared), `infra/` (Tilt/K8s), `docs/`.
- Migración gradual: mover componentes, conservar histórico git.
- CI dividido por paquetes; cache de dependencias por workspace.

## Anexos

- Ver `docs/designs/event-processing.md` para el diseño detallado.
- Ver `docs/performance/benchmark-enqueue.md` para el plan de benchmarking.
