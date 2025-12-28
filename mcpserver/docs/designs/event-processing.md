# Diseño de Solución: Event Processing

## Objetivo

Procesar eventos por `name` con idempotencia y transiciones de estado, localmente o delegando a nodos externos vía gRPC.

## Opción A: Procesamiento Local por Nombre

- Registro `handlers`: `dict[str, Callable[[Event], Awaitable[Result[...] ]]]`.
- `DispatcherUseCase` selecciona handler por `event.name`.
- Flujo:
  1. Enqueue (CREATED)
  2. Publicar a cola local (Redis Stream)
  3. Worker interno consume → `PROCESSING` → handler → `COMPLETED/FAILED`
- Pros: baja latencia, menor complejidad operativa.
- Contras: acoplamiento, escalado limitado.

## Opción B: Delegación gRPC (Nodos/Workers)

- `Router` decide si enviar a `grpc://worker-X` según `event.name`/policy.
- Contrato gRPC:
  - `ProcessEvent(EventMessage) returns (ProcessResult)`
  - `EventMessage`: id, name, payload, context
  - `ProcessResult`: status, result, error_detail
- Flujo:
  1. Enqueue (CREATED)
  2. Publicar a broker (Redis/Kafka)
  3. Gateway gRPC enruta a worker; workers actualizan estado vía API/UoW
- Pros: aislamiento, escalabilidad horizontal, despliegue independiente.
- Contras: mayor complejidad (networking, contratos, observabilidad).

## Elementos Comunes

- Idempotencia: `save_or_resolve_one()` garantiza único registro por (id/external_uuid).
- Transiciones válidas: `transition_event()` define grafo de estados.
- Observabilidad: logs estructurados, métricas (latencia, errores por handler).

## DTOs y Contratos (borrador)

- `ProcessEventInput`: id, name, payload, context
- `ProcessEventOutput`: status (COMPLETED/FAILED), result, error_detail
- gRPC `.proto` (borrador):

```
service EventWorker {
  rpc ProcessEvent (EventMessage) returns (ProcessResult);
}

message EventMessage {
  string id = 1;
  string name = 2;
  string payload = 3; // JSON
  string context = 4; // JSON
}

message ProcessResult {
  string status = 1; // COMPLETED/FAILED
  string result = 2; // JSON
  string error_detail = 3; // JSON
}
```

## Decisión Recomendada (Fase POC)

- Implementar **A** primero (local handlers) para acelerar valor.
- Añadir capa de **Router** con bandera por `event.name` para derivar a **B**.
- Benchmark ambos bajo carga (ver `docs/performance/benchmark-enqueue.md`).

## Próximos Pasos

- Especificar `handlers` mínimos (e.g., `ProcessCourseEvent`).
- Añadir `Worker` asíncrono con Redis Streams.
- Diseñar `Router` con política simple (tabla de decisión por nombre).
- Prototipo gRPC worker (Python/grpcio) y gateway (FastAPI).
