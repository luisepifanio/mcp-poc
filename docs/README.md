# Documentación - MCP POC Monorepo

Índice de documentación técnica del proyecto.

---

## 📚 Documentos Principales

### Para Empezar

1. **[Agents.md](../Agents.md)** - 🎯 **START HERE**
   - Guía principal del monorepo
   - Quick start completo
   - Overview de proyectos
   - Workflows de desarrollo

2. **[SETUP.md](SETUP.md)** - 🔧 Setup Detallado
   - Instalación paso a paso
   - Pre-requisitos
   - Configuración de herramientas
   - Troubleshooting completo

---

### Arquitectura y Diseño

3. **[ARCHITECTURE.md](ARCHITECTURE.md)** - 🏗️ Arquitectura
   - Stack tecnológico
   - Microservicios
   - Clean Architecture
   - Networking
   - ADRs (Architectural Decision Records)

4. **[NETWORK_ARCHITECTURE.md](NETWORK_ARCHITECTURE.md)** - 🌐 Red y Networking
   - Diagrama de flujo de requests
   - Componentes de red (Ingress, Service, Pods)
   - Path rewriting
   - Debugging de networking

---

### Deployment y Operaciones

5. **[DEPLOYMENT.md](DEPLOYMENT.md)** - 🚀 Deployment
   - Entornos (dev, staging, prod)
   - Estrategias (rolling, blue-green, canary)
   - CI/CD pipeline
   - Rollback
   - Monitoreo

6. **[INFRASTRUCTURE_SETUP_SUMMARY.md](INFRASTRUCTURE_SETUP_SUMMARY.md)** - 📊 Resumen de Setup
   - Cambios recientes (2026-01-08)
   - Configuración de Ingress
   - Checklist de validación

---

## 🎯 Guía de Lectura por Rol

### Nuevo Developer

1. [Agents.md](../Agents.md) - Entender el proyecto
2. [SETUP.md](SETUP.md) - Configurar entorno
3. [ARCHITECTURE.md](ARCHITECTURE.md) - Comprender arquitectura
4. Documentación específica:
   - [gateway-api/Agents.md](../gateway-api/Agents.md)
   - [mcpserver/Agents.md](../mcpserver/Agents.md)

### DevOps / SRE

1. [INFRASTRUCTURE_SETUP_SUMMARY.md](INFRASTRUCTURE_SETUP_SUMMARY.md) - Estado actual
2. [NETWORK_ARCHITECTURE.md](NETWORK_ARCHITECTURE.md) - Networking
3. [DEPLOYMENT.md](DEPLOYMENT.md) - Estrategias de deployment
4. [SETUP.md](SETUP.md#troubleshooting) - Troubleshooting

### Arquitecto

1. [ARCHITECTURE.md](ARCHITECTURE.md) - Decisiones arquitectónicas
2. [DEPLOYMENT.md](DEPLOYMENT.md) - Estrategias
3. [NETWORK_ARCHITECTURE.md](NETWORK_ARCHITECTURE.md) - Networking

### QA / Testing

1. [Agents.md](../Agents.md#testing) - Estrategias de testing
2. [gateway-api/Agents.md](../gateway-api/Agents.md#testing) - Tests específicos
3. [mcpserver/Agents.md](../mcpserver/Agents.md#testing) - Tests específicos

---

## 🔍 Quick Reference

### Comandos Útiles

```bash
# Setup inicial
tilt up

# Validar infraestructura
./scripts/validate-setup.sh

# Ver logs
kubectl logs -l app=gateway-api --tail=50 -f

# Troubleshooting
kubectl get pods --all-namespaces
kubectl describe pod -l app=gateway-api
```

### URLs Importantes

- **API Gateway**: http://localhost/api/ping
- **Tilt UI**: http://localhost:10350
- **API Docs**: http://localhost:8000/docs (port-forward)

---

## 📁 Estructura de Documentación

```
docs/
├── README.md                          # Este archivo (índice)
├── SETUP.md                           # Setup detallado
├── ARCHITECTURE.md                    # Arquitectura general
├── NETWORK_ARCHITECTURE.md            # Networking detallado
├── DEPLOYMENT.md                      # Deployment y CI/CD
└── INFRASTRUCTURE_SETUP_SUMMARY.md    # Resumen de cambios recientes
```

---

## 🔗 Documentación Externa

- **Tilt**: https://docs.tilt.dev/
- **Kubernetes**: https://kubernetes.io/docs/
- **NGINX Ingress**: https://kubernetes.github.io/ingress-nginx/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Clean Architecture**: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html

---

## 🤝 Contribuir a la Documentación

Al agregar nueva documentación:

1. Crear archivo en `/docs` con nombre descriptivo
2. Usar formato Markdown con estructura clara
3. Agregar link a este índice
4. Referenciar desde documentos relacionados
5. Actualizar tabla de contenidos

**Estilo**:
- Usar emojis para iconos (📚 🔧 🚀)
- Incluir ejemplos de código
- Agregar diagramas cuando sea útil
- Mantener secciones cortas y enfocadas

---

## 📝 Historial de Documentación

| Fecha      | Documento                            | Cambio                             |
| ---------- | ------------------------------------ | ---------------------------------- |
| 2026-01-08 | INFRASTRUCTURE_SETUP_SUMMARY.md      | Setup inicial de Ingress + k8s     |
| 2026-01-08 | NETWORK_ARCHITECTURE.md              | Diagrama de networking             |
| 2026-01-08 | SETUP.md, ARCHITECTURE.md, DEPLOYMENT.md | Documentación base del monorepo |
| 2026-01-08 | Agents.md (raíz)                     | Guía principal del monorepo        |

---

**¿Primera vez en el proyecto?** → Empieza con [Agents.md](../Agents.md)
