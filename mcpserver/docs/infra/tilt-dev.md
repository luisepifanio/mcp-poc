# Tilt Dev - Infraestructura como Código (Local)

## Objetivo

Levantar entorno local completo (API, DB, Redis, Workers) con live reload y logs centralizados para acelerar desarrollo.

## Componentes

- API (FastAPI): `uv run fastapi dev`
- DB (SQLite/Postgres): contenedor opcional
- Redis: broker para colas/eventos
- Workers: consumidores de eventos (local/gRPC gateway)

## Tiltfile (borrador)

- Definir recursos: `api`, `redis`, `postgres` (opcional), `worker`
- Comandos de build/run:
  - API: `uv run fastapi dev`
  - Worker: `uv run python -m app.infrastructure.redis.main`
- Live reload: monitorear `app/**`, `tests/**`
- Health checks: endpoints `/ping`, conexión a Redis

## Pasos Siguientes

1. Crear `Tiltfile` en raíz del monorepo.
2. Añadir `tilt_configs/` con YAMLs por servicio.
3. Ejecutar `tilt up` y validar estado de recursos.
4. Documentar flujos de desarrollo con Tilt (logs, port forwards, edit-sync).
