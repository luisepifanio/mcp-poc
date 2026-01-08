#!/bin/bash
# Script para configurar /etc/hosts para desarrollo local
# Uso: sudo ./scripts/setup-local-hosts.sh
#
# NOTA: Docker Desktop en macOS NO resuelve correctamente hosts de /etc/hosts
# Este script se mantiene para compatibilidad con clusters externos (minikube, k3s, GKE)
# Para Docker Desktop usa: http://localhost/api/ping

set -e

HOST_ENTRY="127.0.0.1 app-local.hades.ar"

echo "⚠️  ADVERTENCIA: Docker Desktop Limitation"
echo "Docker Desktop en macOS no resuelve /etc/hosts del sistema host."
echo "Este script es útil para clusters externos (minikube, k3s, GKE)"
echo "pero NO funcionará con Docker Desktop."
echo ""
echo "Para Docker Desktop usa: http://localhost/api/ping"
echo ""
read -p "¿Continuar de todas formas? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operación cancelada."
    exit 0
fi

# Verificar si ya existe la entrada
if grep -q "app-local.hades.ar" /etc/hosts; then
    echo "✓ El dominio app-local.hades.ar ya está configurado en /etc/hosts"
else
    echo "Agregando app-local.hades.ar a /etc/hosts..."
    echo "$HOST_ENTRY" | sudo tee -a /etc/hosts > /dev/null
    echo "✓ Dominio agregado exitosamente"
fi

echo ""
echo "Endpoints configurados (solo funcionan fuera de Docker Desktop):"
echo "  curl http://app-local.hades.ar/api/ping"
echo ""
echo "Para Docker Desktop usa:"
echo "  curl http://localhost/api/ping"
echo "  curl http://127.0.0.1/api/ping"
