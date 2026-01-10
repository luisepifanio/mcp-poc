# Infrastructure Audit - MCP POC Monorepo

**Fecha**: 9 de enero de 2026  
**Auditor**: Arquitecto de Infraestructura  
**Alcance**: Análisis de consistencia entre Tiltfile, k8s manifests y documentación

---

## 🎯 Resumen Ejecutivo

Se identificaron **5 inconsistencias críticas** en la infraestructura actual que requieren corrección inmediata para garantizar estabilidad en desarrollo y deployment.

### Estado General

| Componente | Estado | Prioridad |
|------------|--------|-----------|
| NGINX Ingress Controller | ⚠️ Configuración incorrecta | **CRÍTICA** |
| Redis Stream | ⚠️ No documentado | ALTA |
| Ingress SSL Redirect | ⚠️ Mal configurado | ALTA |
| Tilt Port Forwarding | ⚠️ Innecesario | MEDIA |
| Documentación | ⚠️ Desactualizada | ALTA |

---

## 📊 Inconsistencias Detectadas

### 1. NGINX Ingress Controller - Provider Incorrecto

**Severidad**: 🔴 CRÍTICA

**Ubicación**: [Tiltfile](../Tiltfile#L5)

**Problema**:
```python
# ACTUAL (CORRECTO para Docker Desktop + KIND)
cmd='kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.14.1/deploy/static/provider/kind/deploy.yaml'
```

**Análisis actualizado**:
1. ✅ **Provider correcto**: Docker Desktop usa KIND como cluster provisioning method
2. ✅ **KIND provider es el adecuado**: Usa hostPort para exponer 80/443 en localhost
3. ❌ **Cloud provider NO funciona**: Requiere LoadBalancer externo real (GCP/AWS/Azure)

**Confirmación**:
- Docker Desktop Settings muestran "kind" seleccionado como provisioning method
- `kubectl get nodes` muestra `providerID: kind://docker/desktop/...`
- KIND manifest incluye `hostPort: 80` y `hostPort: 443` en el deployment

**Conclusión**: ✅ **NO REQUIERE CAMBIOS** - La configuración actual es correcta.

**Referencias**:
- [Agents.md línea 197](../Agents.md#L197) menciona provider `cloud`
- [NETWORK_ARCHITECTURE.md](NETWORK_ARCHITECTURE.md#L104) menciona v1.10.0

---

### 2. Redis Stream - Documentación Desactualizada

**Severidad**: 🟡 ALTA

**Ubicación**: Múltiple

**Problema**:
Redis Stream está **completamente implementado** en la infraestructura, pero la documentación lo marca como "futuro":

**Evidencia de Implementación**:
- ✅ [k8s/redis-stream.yaml](../k8s/redis-stream.yaml) - Manifest completo con Deployment, Service, PVC, ConfigMap, Secret
- ✅ [Tiltfile línea 13](../Tiltfile#L13) - `"redis-stream"` incluido en services array
- ✅ [k8s/gateway-api.yaml línea 87-96](../k8s/gateway-api.yaml#L87) - Gateway API usa variables REDIS_HOST/REDIS_PORT
- ✅ [Tiltfile línea 23](../Tiltfile#L23) - `resource_deps=['nginx-ingress-controller', 'redis-stream']`

**Documentación Desactualizada**:
- ❌ [Agents.md línea 11](../Agents.md#L11) - Stack tecnológico NO menciona Redis
- ❌ [docs/ARCHITECTURE.md línea 50](ARCHITECTURE.md#L50) - Diagrama muestra Redis como "futuro" con color rojo
- ❌ [docs/ARCHITECTURE.md línea 136](ARCHITECTURE.md#L136) - Sección "Futuro: usar Istio o Linkerd"

**Realidad Actual**:
```yaml
# gateway-api/k8s manifest
env:
  - name: REDIS_HOST
    valueFrom:
      configMapKeyRef:
        name: redis-stream-configuration
        key: REDIS_HOST  # ← REDIS YA ESTÁ EN USO
  - name: REDIS_PORT
    valueFrom:
      configMapKeyRef:
        name: redis-stream-configuration
        key: REDIS_PORT
```

**Impacto**:
- Confusión para nuevos desarrolladores
- Diagramas arquitectónicos incorrectos
- Planificación errónea de features

**Solución Recomendada**:
1. Actualizar [Agents.md](../Agents.md) para incluir Redis en stack
2. Actualizar diagrama en [ARCHITECTURE.md](ARCHITECTURE.md) para mostrar Redis como componente actual
3. Documentar propósito de Redis Stream (event queueing, caching, etc.)

---

### 3. Ingress SSL Redirect sin TLS Configurado

**Severidad**: 🟡 ALTA

**Ubicación**: [k8s/ingress.yaml línea 7](../k8s/ingress.yaml#L7)

**Problema**:
```yaml
annotations:
  nginx.ingress.kubernetes.io/ssl-redirect: "true"  # ← PELIGROSO
```

**Issues**:
1. ❌ SSL redirect habilitado sin certificado TLS
2. ❌ No hay sección `spec.tls` en el Ingress
3. ❌ Causará loops de redirección o errores HTTP 308

**Consecuencias Observables**:
- `curl http://localhost/api/ping` puede fallar con 308 Permanent Redirect
- NGINX intentará redirigir a HTTPS que no existe
- Debugging confuso para usuarios

**Solución Inmediata**:
```yaml
annotations:
  kubernetes.io/ingress.class: "nginx"
  # REMOVER: nginx.ingress.kubernetes.io/ssl-redirect: "true"
  nginx.ingress.kubernetes.io/rewrite-target: /$2
  # ... resto de annotations
```

**Solución Futura (con TLS)**:
```yaml
spec:
  tls:
    - hosts:
        - app-local.hades.ar
      secretName: tls-certificate
  rules:
    # ... resto
```

---

### 4. Tilt Port Forwarding Innecesario

**Severidad**: 🟢 MEDIA

**Ubicación**: [Tiltfile línea 21](../Tiltfile#L21)

**Problema**:
```python
k8s_resource(
    workload="gateway-api", 
    port_forwards="8000:80",  # ← CONFUSO y posiblemente incorrecto
```

**Issues**:
1. ⚠️ **Mapeo confuso**: Forward local:8000 → Service:80
2. ⚠️ **Redundante**: Ingress ya expone en `localhost:80`
3. ⚠️ **No documentado**: Ningún doc menciona este forward

**Impacto**:
- Confusión sobre qué puerto usar
- ¿`localhost:8000` o `localhost:80/api/ping`?
- Resource overhead innecesario

**Opciones**:

**A) Mantener (si se usa para debugging directo)**:
```python
port_forwards="8000:8000"  # local:8000 → container:8000 (bypass Ingress)
```

**B) Remover (si solo se usa Ingress)**:
```python
k8s_resource(
    workload="gateway-api",
    # Sin port_forwards - solo usar Ingress
    labels=['gateway-api'],
    resource_deps=['nginx-ingress-controller', 'redis-stream']
)
```

**Recomendación**: **Opción B** - Usar exclusivamente Ingress para simular producción.

---

### 5. Versiones de NGINX Ingress Inconsistentes

**Severidad**: 🟢 BAJA

**Ubicación**: Múltiple

**Inconsistencia**:
- [Tiltfile](../Tiltfile#L5): `controller-v1.14.1`
- [docs/NETWORK_ARCHITECTURE.md](NETWORK_ARCHITECTURE.md#L104): `controller-v1.10.0`
- [Agents.md](../Agents.md#L197): `controller-v1.10.0`

**Problema**:
- Documentación referencia versión antigua
- No está claro cuál es la versión target

**Solución**:
1. Decidir versión estándar (recomendado: **v1.14.1** - más reciente)
2. Actualizar toda la documentación con esa versión
3. Agregar nota de versionado en README

---

## 🔧 Plan de Remediación

### Fase 1: Correcciones Críticas (Inmediato)

**Duración estimada**: 30 minutos

1. ✅ **Corregir NGINX Ingress Controller en Tiltfile**
   - Cambiar provider de `kind` a `cloud`
   - Mantener versión v1.14.1

2. ✅ **Remover SSL redirect de Ingress**
   - Eliminar annotation peligrosa
   - Documentar decisión

3. ✅ **Ajustar o remover port forwarding**
   - Definir estrategia de acceso
   - Documentar en SETUP.md

### Fase 2: Actualización de Documentación (1 hora)

4. ✅ **Actualizar docs/ARCHITECTURE.md**
   - Mover Redis de "futuro" a "actual"
   - Actualizar diagrama Mermaid
   - Documentar uso de Redis Stream

5. ✅ **Actualizar Agents.md**
   - Agregar Redis al stack tecnológico
   - Corregir versiones de NGINX
   - Actualizar tabla de tecnologías

6. ✅ **Actualizar docs/NETWORK_ARCHITECTURE.md**
   - Sincronizar versión de NGINX
   - Agregar sección de Redis
   - Documentar decisión de SSL

### Fase 3: Validación (30 minutos)

7. ✅ **Testing completo**
   ```bash
   tilt down
   tilt up
   curl http://localhost/api/ping
   kubectl get all
   ```

8. ✅ **Verificar logs**
   ```bash
   kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
   kubectl logs -l app=gateway-api
   kubectl logs -l app=redis-stream
   ```

---

## 📋 Checklist de Validación

Después de aplicar correcciones, verificar:

- [ ] NGINX Ingress Controller usa provider `cloud`
- [ ] `curl http://localhost/api/ping` responde `"pong"`
- [ ] Sin redirecciones 308 a HTTPS
- [ ] Redis Stream en estado `Running`
- [ ] Gateway API se conecta a Redis (verificar logs)
- [ ] Toda la documentación menciona Redis como componente actual
- [ ] Versiones de NGINX consistentes en todos los docs
- [ ] Diagramas arquitectónicos actualizados

---

## 📚 Referencias

- [Kubernetes Ingress NGINX Docs](https://kubernetes.github.io/ingress-nginx/)
- [Docker Desktop Kubernetes](https://docs.docker.com/desktop/kubernetes/)
- [Tilt Best Practices](https://docs.tilt.dev/best_practices.html)
- [Redis Streams](https://redis.io/docs/data-types/streams/)

---

## 🤝 Responsabilidades

| Rol | Responsabilidad |
|-----|-----------------|
| **DevOps** | Aplicar correcciones en Tiltfile y k8s manifests |
| **Tech Writer** | Actualizar documentación según hallazgos |
| **QA** | Validar testing checklist |
| **Team Lead** | Aprobar cambios y coordinar deployment |

---

**Próximos Pasos**: Proceder con Fase 1 del Plan de Remediación.
