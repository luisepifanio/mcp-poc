#!/bin/bash
# Script para configurar /etc/hosts para desarrollo local
# Uso: sudo ./scripts/setup-local-hosts.sh

set -e

HOST_ENTRY="127.0.0.1 app-local.hades.ar"

echo "🔧 Configurando dominio local para desarrollo"
echo ""

# Verificar si ya existe la entrada
if grep -q "app-local.hades.ar" /etc/hosts; then
    echo "✓ El dominio app-local.hades.ar ya está configurado en /etc/hosts"
else
    echo "Agregando app-local.hades.ar a /etc/hosts..."
    echo "$HOST_ENTRY" | sudo tee -a /etc/hosts > /dev/null
    echo "✓ Dominio agregado exitosamente"
fi

echo ""
echo "🔄 Refrescando DNS cache..."

# Detectar OS y flush DNS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sudo dscacheutil -flushcache
    sudo killall -HUP mDNSResponder 2>/dev/null || true
    echo "✓ DNS cache refrescado (macOS)"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - intentar diferentes métodos
    if command -v systemd-resolve &> /dev/null; then
        sudo systemd-resolve --flush-caches
        echo "✓ DNS cache refrescado (systemd-resolved)"
    elif command -v systemctl &> /dev/null; then
        sudo systemctl restart NetworkManager 2>/dev/null || true
        echo "✓ DNS cache refrescado (NetworkManager)"
    else
        echo "⚠️  No se pudo determinar cómo refrescar DNS cache automáticamente"
        echo "   Reinicia manualmente el servicio de red si es necesario"
    fi
else
    echo "⚠️  OS no soportado para flush DNS automático: $OSTYPE"
    echo "   Refresca el DNS cache manualmente"
fi

echo ""
echo "✅ Configuración completa"
echo ""
echo "Endpoints disponibles:"
echo "  curl http://localhost/api/ping"
echo "  curl http://127.0.0.1/api/ping"
echo "  curl http://app-local.hades.ar/api/ping"
echo ""
echo "Nota: Si app-local.hades.ar no funciona, ejecuta manualmente:"
echo "  macOS:  sudo dscacheutil -flushcache"
echo "  Linux:  sudo systemd-resolve --flush-caches"
