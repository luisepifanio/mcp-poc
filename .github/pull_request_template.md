# Descripción del Cambio

- [ ] Tipo de cambio: Feature / Fix / Docs / Infra / Refactor
- [ ] Alcance: Monorepo / gateway-api / mcpserver / mcpagent / docs

## Contexto y Motivación

- ¿Qué problema resuelve?
- ¿Qué motivación o requerimiento atiende?

## Checklist de Calidad

- [ ] Tests unitarios agregados/actualizados cuando aplica
- [ ] Tests funcionales o de integración cuando aplica
- [ ] `ruff check` y `mypy` sin errores
- [ ] Documentación actualizada (README/Agents/Docs)
- [ ] Endpoints y cambios de red documentados

## Convenciones de Documentación

- [ ] Diagramas en Mermaid (obligatorio para todos los diagramas)
- [ ] Si se agrega documentación nueva, está ubicada bajo `docs/` (o enlazada explícitamente desde `README.md` o `Agents.md`)
- [ ] No quedan Markdown huérfanos fuera de `docs/` (o están vinculados desde `README.md`/`Agents.md` si son relevantes)

## Infraestructura (si aplica)

- [ ] Ingress/Servicios/Manifiestos k8s actualizados y probados
- [ ] Tiltfile actualizado y validado con `tilt up`
- [ ] Notas en `docs/NETWORK_ARCHITECTURE.md` y/o `docs/ARCHITECTURE.md` cuando corresponde

## Validación Manual

Comandos utilizados y resultados esperados:

```bash
# Ejemplos
uv run pytest -q
kubectl get pods -A
curl http://localhost/api/ping
```

## Capturas / Diagramas

- Adjuntar diagramas en Mermaid cuando aporte claridad.
