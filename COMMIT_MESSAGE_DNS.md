# docs: Actualizar documentación con solución de DNS flush

## 🎯 Objetivo
Actualizar toda la documentación para reflejar que `app-local.hades.ar` funciona correctamente con DNS cache flush, corrigiendo la suposición incorrecta sobre limitaciones de Docker Desktop.

## 📝 Cambios Realizados

### 1. Corrección de Información Incorrecta
- **Antes**: Documentación indicaba que Docker Desktop no resuelve `/etc/hosts`
- **Después**: Docker Desktop SÍ resuelve `/etc/hosts`, solo requiere flush del DNS cache

### 2. Archivos Actualizados

#### scripts/setup-local-hosts.sh
- ✅ Agregados comandos de DNS flush automático
  - macOS: `dscacheutil -flushcache` + `killall -HUP mDNSResponder`
  - Linux: `systemd-resolve --flush-caches` o `NetworkManager restart`
  - Windows: Nota sobre `ipconfig /flushdns`

#### scripts/validate-setup.sh
- ✅ Agregada validación de endpoint `app-local.hades.ar/api/ping`
- ✅ Verificación de accesibilidad del dominio custom

#### Agents.md (root)
- ✅ Actualizado Quick Start con paso de DNS flush
- ✅ Agregado testing de `app-local.hades.ar` en verificación
- ✅ Actualizada tabla de endpoints con dominio custom
- ✅ Agregada sección de troubleshooting para DNS cache

#### README.md
- ✅ Actualizado Quick Start con dominio custom
- ✅ Agregado `app-local.hades.ar` a tabla de endpoints

#### docs/NETWORK_ARCHITECTURE.md
- ✅ Removida sección incorrecta sobre limitación de Docker Desktop
- ✅ Actualizado diagrama ASCII con endpoint `app-local.hades.ar`
- ✅ Actualizada descripción del Ingress (sin mención a limitaciones)

#### docs/SETUP.md
- ✅ Agregada sección de troubleshooting "app-local.hades.ar no resuelve"
- ✅ Comandos de DNS flush por plataforma
- ✅ Alternativa con `curl --resolve`

#### docs/INFRASTRUCTURE_SETUP_SUMMARY.md
- ✅ Actualizada configuración del Ingress en ejemplos
- ✅ Agregado item en checklist sobre DNS flush
- ✅ Reflejada simplicidad del Ingress (sin hosts específicos)

## 🔍 Descubrimiento
Usuario validó manualmente que:
```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
curl http://app-local.hades.ar/api/ping
```

Funciona correctamente, lo que demuestra que Docker Desktop resuelve `/etc/hosts` sin problemas.

## ✅ Resultado
- Documentación 100% precisa sobre DNS local
- Scripts automatizados incluyen DNS flush
- Troubleshooting completo para problemas de DNS
- No más referencias a limitaciones inexistentes

## 📚 Referencias
- PR anterior: commit b94161e (setup inicial de infraestructura)
- Testing: `curl localhost/api/ping` y `curl app-local.hades.ar/api/ping` ambos funcionan

---
**Tipo**: docs (Documentation)
**Scope**: monorepo-wide
**Breaking Change**: No
