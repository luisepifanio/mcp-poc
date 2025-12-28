# Transición a Monorepo Formal

## Objetivo

Estructurar el proyecto en un monorepo que facilite despliegue de múltiples servicios (API, workers, gateways) y librerías compartidas.

## Estructura Propuesta

```
monorepo/
├── apps/
│   ├── api/               # MCP Server Backend
│   ├── workers/           # Procesadores gRPC/colas
│   └── gateway/           # API/gRPC Gateway
├── libs/
│   ├── domain/            # Entidades y use cases compartidos
│   └── common/            # Utils, Result type, logging
├── infra/
│   ├── tilt/              # Tiltfile y configs locales
│   └── k8s/               # Manifests para despliegue
└── docs/
    ├── performance/
    ├── designs/
    └── roadmap.md
```

## Pasos de Migración

1. Crear repositorios lógicos (apps/libs/infra/docs) sin mover código aún.
2. Migrar `app/` actual a `apps/api/` y ajustar imports/path.
3. Extraer `Result`, `entities` comunes a `libs/domain`.
4. Añadir `infra/tilt` y `Tiltfile` para entorno local.
5. Configurar CI por workspace (lint, type check, tests).

## Consideraciones

- Mantener historia Git: `git mv`.
- Asegurar rutas relativas/pytest `pythonpath`.
- Publicar librerías internas con `uv`/editable installs.

## Referencias

- Ver `docs/infra/tilt-dev.md` para el entorno local.
- Ver `docs/designs/event-processing.md` para arquitectura de workers.
- Ver `docs/performance/benchmark-enqueue.md` para benchmarking.
