#!/bin/bash
# Gateway API Versioning Script
# Usage: ./scripts/version.sh [major|minor|patch]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}ℹ️${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Check if VERSION_TYPE argument is provided
if [ -z "$1" ]; then
    log_error "Version type not provided"
    echo "Usage: $0 [major|minor|patch]"
    echo ""
    echo "Examples:"
    echo "  $0 major   # 0.1.0 → 1.0.0"
    echo "  $0 minor   # 0.1.0 → 0.2.0"
    echo "  $0 patch   # 0.1.0 → 0.1.1"
    exit 1
fi

VERSION_TYPE=$1

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
log_info "Current version: $CURRENT_VERSION"

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Calculate new version
case $VERSION_TYPE in
    major)
        NEW_MAJOR=$((MAJOR + 1))
        NEW_MINOR=0
        NEW_PATCH=0
        ;;
    minor)
        NEW_MAJOR=$MAJOR
        NEW_MINOR=$((MINOR + 1))
        NEW_PATCH=0
        ;;
    patch)
        NEW_MAJOR=$MAJOR
        NEW_MINOR=$MINOR
        NEW_PATCH=$((PATCH + 1))
        ;;
    *)
        log_error "Invalid version type: $VERSION_TYPE"
        echo "Use: major, minor, or patch"
        exit 1
        ;;
esac

NEW_VERSION="$NEW_MAJOR.$NEW_MINOR.$NEW_PATCH"
log_info "New version: $NEW_VERSION"

# Confirm before proceeding
echo ""
read -p "Continue with version bump $CURRENT_VERSION → $NEW_VERSION? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warn "Version bump cancelled"
    exit 0
fi

# Update pyproject.toml
log_info "Updating pyproject.toml..."
sed -i.bak "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
rm -f pyproject.toml.bak
log_success "pyproject.toml updated"

# Update CHANGELOG.md (add new version section)
if [ -f CHANGELOG.md ]; then
    log_info "Updating CHANGELOG.md..."
    
    # Get current date
    TODAY=$(date +%Y-%m-%d)
    
    # Create new version entry in CHANGELOG
    NEW_SECTION="## [$NEW_VERSION] - $TODAY

### Added
- [Add your changes here]

### Fixed
- [Fix any bugs here]

### Changed
- [List breaking changes here]

---

"
    
    # Insert new version after the header
    sed -i.bak "s/^## \[${CURRENT_VERSION}\]/## [$NEW_VERSION] - $TODAY\n\n### Added\n- [Add your changes here]\n\n### Fixed\n- [Fix any bugs here]\n\n### Changed\n- [List breaking changes here]\n\n---\n\n## [$CURRENT_VERSION]/" CHANGELOG.md
    rm -f CHANGELOG.md.bak
    log_success "CHANGELOG.md updated (please review manually)"
fi

# Create git tag
log_info "Creating git tag..."
git add pyproject.toml CHANGELOG.md
git commit -m "chore: bump version to $NEW_VERSION" || log_warn "No changes to commit"
git tag -a "v$NEW_VERSION" -m "Release version $NEW_VERSION" || log_warn "Tag might already exist"
log_success "Git tag created: v$NEW_VERSION"

# Print summary
echo ""
log_success "Version bump complete!"
echo ""
echo "Summary:"
echo "  Old version: $CURRENT_VERSION"
echo "  New version: $NEW_VERSION"
echo "  Git tag: v$NEW_VERSION"
echo ""
echo "Next steps:"
echo "  1. Review CHANGELOG.md (update with actual changes)"
echo "  2. Commit: git commit --amend"
echo "  3. Push: git push origin main && git push origin v$NEW_VERSION"
echo "  4. Create GitHub release with CHANGELOG content"
echo ""
