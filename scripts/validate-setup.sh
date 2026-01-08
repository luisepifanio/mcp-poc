#!/bin/bash
# Script de validación post-setup del monorepo MCP POC
# Verifica que toda la infraestructura esté funcionando correctamente

set -e

echo "🔍 MCP POC - Validación de Infraestructura"
echo "==========================================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para check con output colorido
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1"
        return 1
    fi
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Pre-requisitos
echo "📋 Verificando pre-requisitos..."
echo ""

docker --version > /dev/null 2>&1
check "Docker instalado"

kubectl version --client > /dev/null 2>&1
check "kubectl instalado"

python3 --version > /dev/null 2>&1
check "Python 3 instalado"

uv --version > /dev/null 2>&1
check "uv instalado"

tilt version > /dev/null 2>&1
check "Tilt instalado"

echo ""

# 2. Kubernetes cluster
echo "☸️  Verificando Kubernetes cluster..."
echo ""

kubectl cluster-info > /dev/null 2>&1
check "Kubernetes cluster accesible"

NODE_STATUS=$(kubectl get nodes --no-headers 2>/dev/null | head -n1 | awk '{print $2}')
if [ "$NODE_STATUS" == "Ready" ]; then
    check "Node en estado Ready"
else
    warn "Node status: $NODE_STATUS (esperado: Ready)"
fi

echo ""

# 3. NGINX Ingress Controller
echo "🌐 Verificando NGINX Ingress Controller..."
echo ""

kubectl get namespace ingress-nginx > /dev/null 2>&1
check "Namespace ingress-nginx existe"

INGRESS_POD=$(kubectl get pods -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --no-headers 2>/dev/null | grep "Running" | head -n1 | awk '{print $3}')
if [ "$INGRESS_POD" == "Running" ]; then
    check "NGINX Ingress Controller pod Running"
else
    warn "NGINX Ingress Controller no está Running completamente"
    warn "Ejecuta: tilt up (instalará automáticamente)"
fi

echo ""

# 4. Gateway API
echo "🚀 Verificando Gateway API..."
echo ""

kubectl get deployment gateway-api > /dev/null 2>&1
check "Deployment gateway-api existe"

GATEWAY_POD=$(kubectl get pods -l app=gateway-api --no-headers 2>/dev/null | awk '{print $3}')
if [ "$GATEWAY_POD" == "Running" ]; then
    check "Gateway API pod Running"
else
    echo -e "${RED}✗${NC} Gateway API pod no está Running (estado: $GATEWAY_POD)"
    warn "Ejecuta: tilt up"
fi

kubectl get service gateway-api > /dev/null 2>&1
check "Service gateway-api existe"

SERVICE_TYPE=$(kubectl get service gateway-api -o jsonpath='{.spec.type}' 2>/dev/null)
if [ "$SERVICE_TYPE" == "ClusterIP" ]; then
    check "Service es ClusterIP (correcto)"
else
    echo -e "${YELLOW}⚠${NC} Service es $SERVICE_TYPE (debería ser ClusterIP)"
fi

echo ""

# 5. Ingress Resource
echo "🔀 Verificando Ingress Resource..."
echo ""

kubectl get ingress gateway-ingress > /dev/null 2>&1
check "Ingress gateway-ingress existe"

INGRESS_CLASS=$(kubectl get ingress gateway-ingress -o jsonpath='{.spec.ingressClassName}' 2>/dev/null)
if [ "$INGRESS_CLASS" == "nginx" ]; then
    check "Ingress usa ingressClassName: nginx"
else
    echo -e "${RED}✗${NC} Ingress no tiene ingressClassName correcto (valor: $INGRESS_CLASS)"
fi

echo ""

# 6. Endpoints funcionando
echo "🔗 Verificando endpoints..."
echo ""

# Verificar localhost
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/ping 2>/dev/null || echo "000")
if [ "$RESPONSE" == "200" ]; then
    check "http://localhost/api/ping responde 200"
    
    BODY=$(curl -s http://localhost/api/ping 2>/dev/null)
    if [ "$BODY" == '"pong"' ]; then
        check "Response body es 'pong'"
    else
        echo -e "${RED}✗${NC} Response body incorrecto: $BODY"
    fi
else
    echo -e "${RED}✗${NC} http://localhost/api/ping responde $RESPONSE (esperado: 200)"
    warn "Verifica que Tilt esté corriendo: tilt up"
fi

echo ""

# 7. Tilt
echo "🎯 Verificando Tilt..."
echo ""

if pgrep -x "tilt" > /dev/null 2>&1; then
    check "Tilt está corriendo"
    warn "Tilt UI: http://localhost:10350"
else
    warn "Tilt no está corriendo. Ejecuta: tilt up"
fi

echo ""

# 8. Logs recientes
echo "📜 Revisando logs recientes..."
echo ""

ERROR_COUNT=$(kubectl logs -l app=gateway-api --tail=50 2>/dev/null | grep -i "error\|exception\|fatal" | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    check "No hay errores recientes en logs"
else
    warn "Hay $ERROR_COUNT líneas con errores en logs recientes"
    warn "Revisa: kubectl logs -l app=gateway-api --tail=50"
fi

echo ""

# Resumen final
echo "=========================================="
echo "📊 Resumen de Validación"
echo "=========================================="
echo ""

if [ "$RESPONSE" == "200" ] && [ "$GATEWAY_POD" == "Running" ] && [ "$INGRESS_POD" == "Running" ]; then
    echo -e "${GREEN}✓ Sistema funcionando correctamente${NC}"
    echo ""
    echo "URLs disponibles:"
    echo "  - API: http://localhost/api/ping"
    echo "  - API (IP): http://127.0.0.1/api/ping"
    echo "  - Tilt UI: http://localhost:10350"
    echo "  - Docs: http://localhost:8000/docs (port-forward)"
    echo ""
    echo "Nota: Docker Desktop en macOS no resuelve /etc/hosts del host."
    echo "      Solo usar localhost o 127.0.0.1 para desarrollo local."
    echo ""
    echo "Próximos pasos:"
    echo "  1. Lee la documentación: cat Agents.md"
    echo "  2. Explora Tilt UI: http://localhost:10350"
    echo "  3. Desarrolla features: cd gateway-api && uv run fastapi dev"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Sistema con problemas${NC}"
    echo ""
    echo "Acciones recomendadas:"
    
    if [ "$INGRESS_POD" != "Running" ]; then
        echo "  1. Instalar NGINX Ingress Controller:"
        echo "     kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/cloud/deploy.yaml"
    fi
    
    if [ "$GATEWAY_POD" != "Running" ]; then
        echo "  2. Levantar servicios con Tilt:"
        echo "     tilt up"
    fi
    
    if [ "$RESPONSE" != "200" ]; then
        echo "  3. Ver logs para debug:"
        echo "     kubectl logs -l app=gateway-api --tail=100"
        echo "     kubectl describe pod -l app=gateway-api"
    fi
    
    echo ""
    echo "Ver troubleshooting completo: docs/SETUP.md#troubleshooting"
    echo ""
    exit 1
fi
