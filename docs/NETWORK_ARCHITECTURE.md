# Arquitectura de Red - Implementación Actual

Este documento describe visualmente la arquitectura de networking implementada en el monorepo MCP POC.

---

## 📊 Diagrama de Flujo de Request

```
┌──────────────────────────────────────────────────────────────┐
│                    Developer / Usuario                        │
│                                                               │
│  curl http://localhost/api/ping                               │
│  curl http://127.0.0.1/api/ping                               │
│                                                               │
│  Nota: Docker Desktop NO resuelve dominios de /etc/hosts      │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        │ HTTP Request
                        │ Port 80
                        ↓
┌────────────────────────────────────────────────────────────────┐
│              Docker Desktop - Kubernetes Cluster               │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │        Namespace: ingress-nginx                          │ │
│  │                                                          │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │    NGINX Ingress Controller Pod                    │ │ │
│  │  │    - Escucha en port 80                            │ │ │
│  │  │    - Lee recursos Ingress                          │ │ │
│  │  │    - Routing basado en:                            │ │ │
│  │  │      * Host (localhost, app-local.hades.ar)        │ │ │
│  │  │      * Path (/api/*)                               │ │ │
│  │  │    - Path rewriting: /api/ping → /ping             │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  │                          ↓                               │ │
│  └──────────────────────────┼───────────────────────────────┘ │
│                             │                                 │
│                             │ Internal routing                │
│                             │ to Service                      │
│                             ↓                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │        Namespace: default                                │ │
│  │                                                          │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │    Ingress Resource: gateway-ingress               │ │ │
│  │  │    - ingressClassName: nginx                       │ │ │
│  │  │    - Rules:                                        │ │ │
│  │  │      Host: localhost                               │ │ │
│  │  │        Path: /api(/|$)(.*)                         │ │ │
│  │  │        → Service: gateway-api:80                   │ │ │
│  │  │      Host: app-local.hades.ar                      │ │ │
│  │  │        Path: /api(/|$)(.*)                         │ │ │
│  │  │        → Service: gateway-api:80                   │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  │                          ↓                               │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │    Service: gateway-api                            │ │ │
│  │  │    - Type: ClusterIP                               │ │ │
│  │  │    - ClusterIP: 10.96.xxx.xxx (interno)            │ │ │
│  │  │    - Port: 80                                      │ │ │
│  │  │    - TargetPort: 8000                              │ │ │
│  │  │    - Selector: app=gateway-api                     │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  │                          ↓                               │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │    Pod: gateway-api-xxxxxxxxxx-xxxxx               │ │ │
│  │  │    Labels: app=gateway-api                         │ │ │
│  │  │                                                    │ │ │
│  │  │    ┌──────────────────────────────────────────┐   │ │ │
│  │  │    │  Container: gateway-api                  │   │ │ │
│  │  │    │  - Image: gateway-api:latest             │   │ │ │
│  │  │    │  - Port: 8000                            │   │ │ │
│  │  │    │  - App: FastAPI (uvicorn)                │   │ │ │
│  │  │    │  - Endpoints:                            │   │ │ │
│  │  │    │    * GET /ping → "pong"                  │   │ │ │
│  │  │    │    * GET /docs → Swagger UI              │   │ │ │
│  │  │    └──────────────────────────────────────────┘   │ │ │
│  │  │                                                    │ │ │
│  │  │    ConfigMap: gateway-api-configuration            │ │ │
│  │  │    Secret: gateway-api-credentials                 │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  │                                                          │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                        │
                        │ HTTP Response
                        ↓
┌────────────────────────────────────────────────────────────────┐
│                      Response: "pong"                          │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Desglose de Componentes

### 1. NGINX Ingress Controller

**Namespace**: `ingress-nginx`

**Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ingress-nginx-controller
  namespace: ingress-nginx
```

**Instalación**: Automática vía Tiltfile
```python
local_resource(
    'nginx-ingress-controller',
    cmd='kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/cloud/deploy.yaml'
)
```

**Función**:
- Lee recursos `Ingress` del cluster
- Configura NGINX dinámicamente
- Maneja routing L7 (HTTP/HTTPS)
- Path rewriting
- SSL/TLS termination (futuro)

**Verificar**:
```bash
kubectl get pods -n ingress-nginx
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50
```

---

### 2. Ingress Resource

**Namespace**: `default`

**Archivo**: `k8s/ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: gateway-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx
  rules:
    # Sin host específico - acepta cualquier host
    # Solución para Docker Desktop que no resuelve /etc/hosts
    - http:
        paths:
          - path: /api(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: gateway-api
                port:
                  number: 80
```

**Función**:
- Define reglas de routing
- Path rewriting: `/api/ping` → `/ping`
- Sin restricción de host (acepta localhost, 127.0.0.1, cualquier IP)
- Solución para Docker Desktop que no resuelve `/etc/hosts`

**Verificar**:
```bash
kubectl get ingress
kubectl describe ingress gateway-ingress
```

---

### 3. Service

**Namespace**: `default`

**Archivo**: `k8s/gateway-api.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: gateway-api
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8000
  selector:
    app: gateway-api
```

**Función**:
- Abstracción sobre pods (load balancing interno)
- Endpoint estable (DNS: `gateway-api.default.svc.cluster.local`)
- Port mapping: 80 → 8000

**Verificar**:
```bash
kubectl get svc gateway-api
kubectl describe svc gateway-api
kubectl get endpoints gateway-api
```

---

### 4. Pod

**Namespace**: `default`

**Archivo**: `k8s/gateway-api.yaml` (Deployment)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gateway-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gateway-api
  template:
    metadata:
      labels:
        app: gateway-api
    spec:
      containers:
        - name: gateway-api
          image: gateway-api
          ports:
            - containerPort: 8000
```

**Función**:
- Ejecuta la aplicación FastAPI
- Uvicorn server en port 8000
- Implementa endpoints (`/ping`)

**Verificar**:
```bash
kubectl get pods -l app=gateway-api
kubectl logs -l app=gateway-api --tail=50 -f
kubectl exec -it deployment/gateway-api -- /bin/bash
```

---
## ⚠️ Docker Desktop DNS Limitation

### El Problema

Docker Desktop en macOS **no resuelve correctamente** los hosts configurados en `/etc/hosts` del sistema host. Esto significa que dominios personalizados como `app-local.hades.ar` no funcionarán, aunque estén configurados en `/etc/hosts`.

### Por Qué Sucede

Docker Desktop corre en una VM ligera (HyperKit) que tiene su propio stack de networking. Esta VM no hereda automáticamente el archivo `/etc/hosts` del macOS host.

### Solución para Desarrollo Local

**Usar únicamente `localhost` o `127.0.0.1`**:

```bash
# ✅ Funciona
curl http://localhost/api/ping
curl http://127.0.0.1/api/ping

# ❌ NO funciona (aunque esté en /etc/hosts)
curl http://app-local.hades.ar/api/ping
```

### Alternativa: Forzar Resolución DNS

Si realmente necesitas usar el dominio personalizado, puedes forzar la resolución:

```bash
curl --resolve app-local.hades.ar:80:127.0.0.1 http://app-local.hades.ar/api/ping
```

### En Clusters Externos

Esta limitación **NO aplica** a clusters externos:
- ✅ Minikube
- ✅ k3s
- ✅ GKE
- ✅ AWS EKS
- ✅ Cualquier cluster remoto

En estos entornos, los dominios personalizados funcionan normalmente.

### Configuración del Ingress

Para soportar Docker Desktop, el Ingress está configurado **sin host específico**:

```yaml
spec:
  rules:
    - http:  # Sin campo "host" - acepta cualquier host
        paths:
          - path: /api(/|$)(.*)
```

Esto permite que el Ingress responda a cualquier host (localhost, 127.0.0.1, IP del cluster, etc).

---
## 🚦 Flujo de Resolución DNS

```
1. curl http://localhost/api/ping
           ↓
2. OS resolve "localhost" → 127.0.0.1
           ↓
3. Request to 127.0.0.1:80
           ↓
4. Docker Desktop port mapping → NGINX Ingress Controller
           ↓
5. NGINX lee Ingress rules:
   - Host: localhost ✓
   - Path: /api/ping → matches /api(/|$)(.*)
           ↓
6. Path rewrite: /api/ping → /ping (usando $2 = "ping")
           ↓
7. Forward to Service: gateway-api:80
           ↓
8. k8s DNS resolve: gateway-api.default.svc.cluster.local → 10.96.xxx.xxx
           ↓
9. Service load balance → Pod IP (10.1.0.xx:8000)
           ↓
10. Container recibe request en port 8000
           ↓
11. FastAPI router: GET /ping → return "pong"
           ↓
12. Response: HTTP 200 "pong"
```

---

## 🔀 Comparación: Antes vs Después

### Antes (No Funcionaba)

```
curl http://localhost/api/ping
      ↓
   ❌ No ingress controller
   ❌ Ingress con sintaxis incorrecta
   ❌ Service type NodePort (puerto random)
      ↓
   ❌ Connection refused / 404
```

### Después (Funciona)

```
curl http://localhost/api/ping
      ↓
   ✅ NGINX Ingress Controller instalado
      ↓
   ✅ Ingress con sintaxis correcta
      ↓
   ✅ Service type ClusterIP (port 80 → 8000)
      ↓
   ✅ Pod recibe request en /ping
      ↓
   ✅ Response: "pong"
```

---

## 🌐 Path Rewriting Detallado

### Configuración

```yaml
annotations:
  nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  rules:
    - http:
        paths:
          - path: /api(/|$)(.*)
            pathType: ImplementationSpecific
```

### Ejemplos

| Request Original           | Regex Match    | $2 Captured | Rewritten Path      | Enviado a Pod |
| -------------------------- | -------------- | ----------- | ------------------- | ------------- |
| `/api/ping`                | ✅ `/api/ping` | `ping`      | `/$2` = `/ping`     | `GET /ping`   |
| `/api/users/123`           | ✅             | `users/123` | `/$2` = `/users/123`| `GET /users/123` |
| `/api/`                    | ✅ `/api/`     | `` (empty)  | `/$2` = `/`         | `GET /`       |
| `/api`                     | ✅ `/api`      | `` (empty)  | `/$2` = `/`         | `GET /`       |
| `/other`                   | ❌ (no match)  | -           | -                   | 404           |

### Regex Explicado

```
/api       # Literal "/api"
(/|$)      # Captura grupo 1: "/" o fin de string
(.*)       # Captura grupo 2: cualquier caracter (esto se usa en /$2)
```

**Grupo 1** (`(/|$)`): Maneja tanto `/api/` como `/api`  
**Grupo 2** (`(.*)`): Captura el resto del path (lo que queremos preservar)

---

## 🔐 Security Considerations

### Actual (Desarrollo Local)

- ❌ Sin SSL/TLS (HTTP plaintext)
- ❌ Sin autenticación en Ingress
- ❌ Secrets en base64 (no encriptados)
- ✅ ClusterIP (no expuesto directamente)

### Futuro (Producción)

- ✅ SSL/TLS con Let's Encrypt (cert-manager)
- ✅ OAuth2 Proxy o Auth Middleware
- ✅ Sealed Secrets o External Secrets Operator
- ✅ Network Policies
- ✅ Rate limiting en Ingress

---

## 📈 Escalabilidad

### Actual

```yaml
spec:
  replicas: 1  # Single pod
```

### Futuro (Production)

```yaml
spec:
  replicas: 3  # High availability
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: gateway-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: gateway-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

## 🔍 Debugging Commands

### Ver todo el stack

```bash
# Ingress Controller
kubectl get pods -n ingress-nginx
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50

# Ingress resource
kubectl get ingress
kubectl describe ingress gateway-ingress

# Service
kubectl get svc gateway-api
kubectl describe svc gateway-api

# Pods
kubectl get pods -l app=gateway-api
kubectl logs -l app=gateway-api --tail=50 -f
kubectl describe pod -l app=gateway-api

# Endpoints (Service → Pod mapping)
kubectl get endpoints gateway-api
```

### Probar conectividad interna

```bash
# Desde un pod temporal
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- sh

# Dentro del pod:
curl http://gateway-api.default.svc.cluster.local:80/ping
# Debería responder: "pong"
```

### Inspeccionar configuración de NGINX

```bash
# Ver config generada por Ingress Controller
kubectl exec -n ingress-nginx deployment/ingress-nginx-controller -- cat /etc/nginx/nginx.conf | grep -A 20 "server_name localhost"
```

---

## 📚 Referencias

- [NGINX Ingress Controller Docs](https://kubernetes.github.io/ingress-nginx/)
- [Kubernetes Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Service Types](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types)
- [Path Rewriting](https://kubernetes.github.io/ingress-nginx/examples/rewrite/)
