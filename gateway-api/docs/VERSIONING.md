# Versioning Guide

Gateway API follows [Semantic Versioning (semver)](https://semver.org/spec/v2.0.0.html).

## Version Format

```
MAJOR.MINOR.PATCH
0    .1    .0
```

- **MAJOR**: Breaking API/architecture changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## Current Version

**v0.1.0** - Stable baseline with:

- Configuration management
- API foundation (routers)
- 35 unit tests
- Clean Architecture

## Release Cycle

### Development Phase

1. Create feature branch: `git checkout -b feature/new-feature`
2. Implement and test: `uv run pytest && uv run ruff check .`
3. Create PR with meaningful title

### Release Preparation

1. Review all merged PRs since last release
2. Update CHANGELOG.md with changes
3. Decide version bump (major/minor/patch)
4. Run version script: `bash scripts/version.sh [major|minor|patch]`

### Release Execution

1. Tag automatically created: `v0.2.0`
2. Push tag: `git push origin v0.2.0`
3. GitHub Actions automatically:
   - Runs all tests
   - Builds artifacts
   - Creates release notes

### Post-Release

1. Verify release on GitHub
2. Update documentation if needed
3. Announce in team channels

## Using the Version Script

### Prerequisites

```bash
# Make script executable
chmod +x scripts/version.sh
```

### Bump Major Version

```bash
# 0.1.0 → 1.0.0
bash scripts/version.sh major
```

### Bump Minor Version

```bash
# 0.1.0 → 0.2.0
bash scripts/version.sh minor
```

### Bump Patch Version

```bash
# 0.1.0 → 0.1.1
bash scripts/version.sh patch
```

## CHANGELOG.md Format

```markdown
## [0.2.0] - 2025-01-15

### Added

- Database layer (SQLAlchemy + SQLModel)
- Repository pattern implementation
- 20 new tests

### Fixed

- Configuration reload in tests

### Changed

- Modified lifespan hook signature

---

## [0.1.0] - 2025-01-07

[Previous release details]
```

## Version Planning (Roadmap)

### v0.1.0 (Current) ✅

- [x] Configuration management
- [x] API foundation
- [x] 35 tests, 100% coverage
- [x] Clean Architecture

### v0.2.0 (Next)

- [ ] Database layer
- [ ] Repository pattern
- [ ] UseCase classes
- [ ] 50+ tests

### v0.3.0 (Future)

- [ ] Authentication
- [ ] Error handling
- [ ] Advanced logging
- [ ] 75+ tests

### v1.0.0 (Production Ready)

- [ ] All above features
- [ ] Security audit
- [ ] Performance optimization
- [ ] 100+ tests

## Git Tagging

### Create Tag Manually

```bash
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0
```

### View All Tags

```bash
git tag -l
```

### Delete Tag

```bash
git tag -d v0.1.0
git push origin --delete v0.1.0
```

## CI/CD Integration

The GitHub Actions workflow automatically:

1. Validates tag format: `v*`
2. Runs all tests
3. Verifies coverage
4. Creates release with CHANGELOG content
5. Builds and publishes artifacts

## Version Compatibility

### Backward Compatibility

- **MAJOR** changes: May break existing code
- **MINOR** changes: New features, backward compatible
- **PATCH** changes: Bug fixes, fully compatible

### Breaking Changes

Document clearly in CHANGELOG:

```markdown
### ⚠️ BREAKING CHANGES

- Removed deprecated `old_function()` - use `new_function()` instead
- Changed `AppSettings.env_file` parameter type from str to Optional[str]
```

## Development Stability

### Beta Versions (Pre-release)

For unstable features during development:

```
v0.2.0-beta.1
v0.2.0-beta.2
```

Tag format: `v[MAJOR].[MINOR].[PATCH]-[prerelease]`

## Version Queries

### Current Version

```bash
grep 'version = ' pyproject.toml | cut -d'"' -f2
```

### Last Release Tag

```bash
git describe --tags --abbrev=0
```

### All Commits Since Last Release

```bash
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

## Release Notes Template

````markdown
# Release v0.2.0

**Release Date**: 2025-01-15  
**Python**: 3.12+

## Highlights

- New database layer with SQLAlchemy
- Repository pattern for clean data access
- 20+ new tests

## Full Changelog

[Include CHANGELOG.md content]

## Installation

```bash
pip install mcpserver==0.2.0
```
````

## Getting Help

- 📖 [Documentation](../README.md)
- 🐛 [Report Issues](../../issues)

```

---

## Questions?

- For versioning policy questions, ask the team lead
- For script issues, check `scripts/version.sh` documentation
- For release timing, see project roadmap
```
