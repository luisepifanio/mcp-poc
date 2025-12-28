# Benchmark de Performance - EnqueueEventUseCase (MVP)

## Objetivo

Medir latencia y throughput bajo concurrencia en el flujo de encolado de eventos (idempotente) para validar comportamiento y detectar cuellos de botella.

## Métricas

- p50/p95/p99 de latencia
- Throughput (req/s) promedio y pico
- Tasa de errores/timeouts
- Idempotencia: % de respuestas que retornan el mismo `id` bajo colisión
- Integridad: duplicados en BD (debe ser 0)

## Escenarios

- Baseline: requests secuenciales
- Concurrencia baja: 5-10 usuarios
- Concurrencia media: 50-100 usuarios
- Concurrencia alta: 200-500 usuarios (stress)
- Idempotencia:
  - C1: mismo `external_uuid`
  - C2: mismo `id`
  - C3: `external_uuid` igual, IDs distintos
  - Únicos: todos diferentes (sin colisión)

## Herramienta recomendada

- Locust: tasks separadas por escenario (C1/C2/C3/unique), ramp-up configurable, métricas en UI.
- Alternativa ligera: `hey`/`wrk` para medir puro HTTP (sin lógica de colisión).

## Diseño con Locust

- Users: definir `--users` y `--spawn-rate` según escenario.
- Tasks:
  - `task_unique`: genera UUIDs únicos (latencia “limpia”).
  - `task_c1`: mismo `external_uuid`, IDs únicos.
  - `task_c2`: mismo `id`, `external_uuid` únicos.
  - `task_c3`: mismo `external_uuid`, IDs distintos.
- Pesos: 25% cada task o ejecución aislada por escenario.

## Plan de Ejecución (MVP)

1. Levantar servidor local (`uv run fastapi dev`).
2. Ejecutar Locust con 50 users por 2 minutos.
3. Capturar métricas (latencias, req/s, errores).
4. Validar idempotencia post-run consultando la BD.
5. Iterar con 100/200 users.

## Comandos sugeridos

```bash
# Servidor
uv run fastapi dev

# Locust (ejemplo, una vez exista locustfile)
locust -f perf/locustfile.py --host http://127.0.0.1:8000 --users 50 --spawn-rate 10 --run-time 2m
```

## Verificación post-run

- Consultar registros por `external_uuid`/`id` usados en prueba.
- Confirmar: 1 solo registro por colisión, respuestas retornan mismo `id`.
- Registrar resultados en `docs/performance/results.md`.

## Próximos pasos

- Añadir `perf/locustfile.py` con tasks C1/C2/C3/unique.
- Probar con PostgreSQL (docker) para observar locks/constraints.
- Opcional: profiling ligero (py-spy) en el servidor durante la prueba.
