# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- NGINX Ingress Controller auto-installation in Tiltfile
- Comprehensive monorepo documentation structure:
  - `Agents.md` - Main development guide at monorepo root
  - `docs/SETUP.md` - Detailed setup instructions
  - `docs/ARCHITECTURE.md` - Architectural vision and ADRs
  - `docs/DEPLOYMENT.md` - Deployment strategies
  - `docs/NETWORK_ARCHITECTURE.md` - Networking diagrams and flow
  - `docs/INFRASTRUCTURE_SETUP_SUMMARY.md` - Technical summary
  - `docs/README.md` - Documentation index
- Scripts for automation:
  - `scripts/setup-local-hosts.sh` - /etc/hosts configuration
  - `scripts/validate-setup.sh` - Infrastructure validation
- Mermaid diagrams for better visualization

### Changed
- `k8s/ingress.yaml`: Fixed syntax, added ingressClassName, simplified host rules
- `k8s/gateway-api.yaml`: Service type changed from NodePort to ClusterIP
- `Tiltfile`: Added NGINX Ingress Controller installation and resource dependencies
- `README.md`: Updated with simplified quick start

### Fixed
- NGINX Ingress Controller installation issue
- Ingress path rewriting configuration
- Docker Desktop DNS limitation documented and worked around

### Documented
- Docker Desktop DNS limitation across all relevant documentation
- Complete networking flow from request to response
- Troubleshooting guides for common issues
- ADRs (Architectural Decision Records)

## [0.1.0-alpha] - 2026-01-08

### Initial Release
- Project structure established
- Gateway API microservice (FastAPI)
- MCP Server microservice (FastAPI)
- MCP Agent tooling
- Docker containerization
- Kubernetes manifests
- Tilt development environment

[Unreleased]: https://github.com/username/mcp-poc/compare/v0.1.0-alpha...HEAD
[0.1.0-alpha]: https://github.com/username/mcp-poc/releases/tag/v0.1.0-alpha
