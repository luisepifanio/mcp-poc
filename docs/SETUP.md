# Setup Guide - MCP POC Monorepo

Esta guía proporciona instrucciones detalladas para configurar el entorno de desarrollo del monorepo MCP POC.

---

## 📋 Tabla de Contenidos

1. [Pre-requisitos](#pre-requisitos)
2. [Instalación de Herramientas](#instalación-de-herramientas)
3. [Configuración de Docker Desktop](#configuración-de-docker-desktop)
4. [Setup del Monorepo](#setup-del-monorepo)
5. [Verificación del Setup](#verificación-del-setup)
6. [Troubleshooting](#troubleshooting)

---

## Pre-requisitos

### Sistema Operativo

- **macOS**: 11+ (Big Sur o superior)
- **Linux**: Ubuntu 20.04+, Debian 11+
- **Windows**: WSL2 con Ubuntu

### Hardware Recomendado

- **RAM**: Mínimo 8GB, recomendado 16GB
- **Disco**: 20GB libres
- **CPU**: 4 cores recomendado

---

## Instalación de Herramientas

### 1. Docker Desktop

**macOS**:
```bash
# Descargar desde: https://www.docker.com/products/docker-desktop
# O con Homebrew:
brew install --cask docker

# Iniciar Docker Desktop y habilitar Kubernetes:
# Preferences → Kubernetes → Enable Kubernetes
```

**Linux**:
```bash
# Instalar Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Instalar kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

### 2. Python 3.12+

**macOS**:
```bash
# Con Homebrew
brew install python@3.12

# Verificar instalación
python3 --version
```

**Linux**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip

# Verificar instalación
python3.12 --version
```

### 3. uv (Python Package Manager)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verificar instalación
uv --version
```

### 4. Tilt

```bash
# macOS/Linux
curl -fsSL https://raw.githubusercontent.com/tilt-dev/tilt/master/scripts/install.sh | bash

# Verificar instalación
tilt version
```

### 5. kubectl (si no viene con Docker Desktop)

```bash
# macOS
brew install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verificar instalación
kubectl version --client
```

---

## Configuración de Docker Desktop

### 1. Habilitar Kubernetes

1. Abrir Docker Desktop
2. Ir a **Preferences/Settings**
3. Seleccionar **Kubernetes**
4. Marcar **Enable Kubernetes**
5. Click en **Apply & Restart**
6. Esperar a que el cluster inicie (puede tomar 2-5 minutos)

### 2. Configurar Recursos

**Configuración Recomendada**:
- **CPUs**: 4
- **Memory**: 6GB
- **Swap**: 1GB
- **Disk**: 60GB

Para ajustar:
1. Docker Desktop → Preferences → Resources
2. Ajustar valores
3. Apply & Restart

### 3. Verificar Cluster

```bash
# Ver información del cluster
kubectl cluster-info

# Salida esperada:
# Kubernetes control plane is running at https://kubernetes.docker.internal:6443
# CoreDNS is running at https://kubernetes.docker.internal:6443/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

# Verificar nodes
kubectl get nodes

# Salida esperada:
# NAME             STATUS   ROLES           AGE   VERSION
# docker-desktop   Ready    control-plane   10m   v1.29.x
```

---

## Setup del Monorepo

### 1. Clonar Repositorio

```bash
# Clonar (reemplaza <repo-url> con la URL real)
git clone <repo-url> mcp-poc
cd mcp-poc
```

### 2. Configurar Dominio Local (Opcional)

Este paso es opcional pero recomendado para testing más realista:

```bash
# Ejecutar script de configuración
sudo ./scripts/setup-local-hosts.sh

# Esto agrega: 127.0.0.1 app-local.hades.ar a /etc/hosts
```

### 3. Setup de Proyectos Individuales

**Gateway API**:
```bash
cd gateway-api
uv sync --locked --group dev
cp env.example local.env
# Editar local.env si es necesario
cd ..
```

**MCP Server**:
```bash
cd mcpserver
uv sync --locked --group dev
cp env.example local.env
# Editar local.env si es necesario
cd ..
```

### 4. Levantar Infraestructura con Tilt

```bash
# Desde la raíz del monorepo
tilt up

# Tilt abrirá automáticamente el navegador en http://localhost:10350
# Si no abre, accede manualmente a esa URL
```

**Primera Ejecución**: La primera vez tomará más tiempo porque:
1. Se descarga e instala NGINX Ingress Controller
2. Se construyen las imágenes Docker de cada servicio
3. Se despliegan los pods en k8s

**Tiempo estimado**: 3-5 minutos en la primera ejecución, luego ~30 segundos.

---

## Verificación del Setup

### 1. Verificar Tilt UI

Abrir http://localhost:10350 y verificar que todos los recursos estén en verde:

- `nginx-ingress-controller` (verde)
- `gateway-api` (verde)
- `gateway-ingress` (verde)

### 2. Verificar Pods en k8s

```bash
# Ver pods del namespace default
kubectl get pods

# Salida esperada:
# NAME                           READY   STATUS    RESTARTS   AGE
# gateway-api-xxxxxxxxxx-xxxxx   1/1     Running   0          2m

# Ver pods del ingress controller
kubectl get pods -n ingress-nginx

# Salida esperada:
# NAME                                        READY   STATUS    RESTARTS   AGE
# ingress-nginx-controller-xxxxxxxxxx-xxxxx   1/1     Running   0          3m
```

### 3. Probar Endpoints

```bash
# Test básico con localhost
curl http://localhost/api/ping

# Salida esperada: "pong"

# Test con dominio local (si configuraste /etc/hosts)
curl http://app-local.hades.ar/api/ping

# Salida esperada: "pong"
```

### 4. Verificar Logs

**En Tilt UI**:
- Click en `gateway-api` para ver logs en tiempo real

**En kubectl**:
```bash
# Ver logs del gateway-api
kubectl logs -l app=gateway-api --tail=50 -f

# Ver logs del ingress controller
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50
```

---

## Troubleshooting

### Docker Desktop no inicia Kubernetes

**Síntomas**: Kubernetes muestra estado "Starting" por más de 10 minutos

**Solución**:
```bash
# Reset Kubernetes cluster
# Docker Desktop → Preferences → Kubernetes → Reset Kubernetes Cluster

# O en línea de comandos (macOS):
rm -rf ~/.kube
# Luego reiniciar Docker Desktop
```

### NGINX Ingress Controller no se instala

**Síntomas**: Error en Tilt al instalar ingress controller

**Solución**:
```bash
# Instalar manualmente
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/cloud/deploy.yaml

# Esperar a que esté ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

# Luego ejecutar tilt up de nuevo
```

### Pod gateway-api en CrashLoopBackOff

**Diagnóstico**:
```bash
# Ver logs del pod
kubectl logs -l app=gateway-api --tail=100

# Ver eventos
kubectl describe pod -l app=gateway-api
```

**Causas comunes**:
1. **Imagen no buildeó correctamente**:
   ```bash
   cd gateway-api
   docker build -t gateway-api:debug .
   ```

2. **Puerto incorrecto**:
   - Verificar que `containerPort: 8000` en [k8s/gateway-api.yaml](../k8s/gateway-api.yaml)
   - Verificar que FastAPI use puerto 8000 en el Dockerfile

3. **Dependencias faltantes**:
   ```bash
   cd gateway-api
   uv sync --locked --group dev
   ```

### curl localhost/api/ping devuelve 404

**Diagnóstico**:
```bash
# Verificar que el ingress esté configurado
kubectl get ingress

# Ver detalles del ingress
kubectl describe ingress gateway-ingress
```

**Causas comunes**:
1. **NGINX Ingress Controller no corriendo**: Ver sección anterior
2. **Path incorrecto**: Verificar [k8s/ingress.yaml](../k8s/ingress.yaml)
3. **Service no existe**:
   ```bash
   kubectl get svc gateway-api
   ```

### app-local.hades.ar no resuelve

**Síntoma**: `curl: (6) Could not resolve host: app-local.hades.ar`

**Causa**: DNS cache no actualizado después de modificar `/etc/hosts`

**Solución**:
```bash
# macOS
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder

# Linux (systemd-resolved)
sudo systemd-resolve --flush-caches

# Linux (NetworkManager)
sudo systemctl restart NetworkManager

# Verificar
curl http://app-local.hades.ar/api/ping
```

**Alternativa rápida** (sin flush):
```bash
curl --resolve app-local.hades.ar:80:127.0.0.1 http://app-local.hades.ar/api/ping
```

**Nota**: El script `./scripts/setup-local-hosts.sh` hace el flush automáticamente.

### "Permission denied" al ejecutar scripts

```bash
# Dar permisos de ejecución
chmod +x ./scripts/*.sh
```

### uv sync falla con error de git

**Síntoma**: Error "git not found" o similar

**Solución**:
```bash
# macOS
brew install git

# Linux
sudo apt install git
```

### Tilt muestra "waiting for dependencies"

**Síntoma**: Recursos bloqueados esperando dependencias

**Diagnóstico**:
```bash
# Ver recursos en Tilt
tilt get uiresource

# Verificar orden de dependencias en Tiltfile
cat Tiltfile | grep resource_deps
```

**Solución**: Verificar que `nginx-ingress-controller` esté en estado verde antes que otros recursos.

---

## Próximos Pasos

Una vez completado el setup:

1. **Leer documentación específica**:
   - [gateway-api/Agents.md](../gateway-api/Agents.md)
   - [mcpserver/Agents.md](../mcpserver/Agents.md)

2. **Explorar arquitectura**: [ARCHITECTURE.md](ARCHITECTURE.md)

3. **Desarrollar tu primera feature**:
   ```bash
   cd gateway-api
   uv run fastapi dev  # Desarrollo local sin k8s
   ```

4. **Ejecutar tests**:
   ```bash
   cd gateway-api
   uv run pytest -v
   ```

---

## Recursos Adicionales

- **Tilt Docs**: https://docs.tilt.dev/
- **Docker Desktop k8s**: https://docs.docker.com/desktop/kubernetes/
- **NGINX Ingress Controller**: https://kubernetes.github.io/ingress-nginx/
- **FastAPI**: https://fastapi.tiangolo.com/
- **uv Documentation**: https://docs.astral.sh/uv/
