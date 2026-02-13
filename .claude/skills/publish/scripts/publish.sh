#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$(git rev-parse --show-toplevel)"

ACTION="${1:-publish}"

get_version() {
    grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/'
}

bump_version() {
    local part="${1:-patch}"
    local version
    version=$(get_version)
    IFS='.' read -r major minor patch <<< "$version"

    case "$part" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
        *) echo -e "${RED}Unknown part: $part (use major, minor, patch)${NC}"; exit 1 ;;
    esac

    local new_version="${major}.${minor}.${patch}"
    sed -i "s/^version = \".*\"/version = \"${new_version}\"/" pyproject.toml
    echo -e "${GREEN}${version} → ${new_version}${NC}"
}

if [ "$ACTION" = "bump" ]; then
    bump_version "${2:-patch}"
    exit 0
fi

# Load .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Validate token
if [ -z "$PYPI_TOKEN" ]; then
    echo -e "${RED}PYPI_TOKEN not found in .env${NC}"
    exit 1
fi

# Auto-bump patch version
bump_version patch

VERSION=$(get_version)
echo -e "${YELLOW}Publishing version ${VERSION}...${NC}"

echo -e "${YELLOW}Running linters...${NC}"
uv run ruff check src/
uv run mypy src/

echo -e "${YELLOW}Running tests...${NC}"
uv run pytest || [ $? -eq 5 ]

echo -e "${YELLOW}Cleaning dist/...${NC}"
rm -rf dist/

echo -e "${YELLOW}Building package...${NC}"
uv build

echo -e "${YELLOW}Publishing to PyPI...${NC}"
uv publish --token "$PYPI_TOKEN"

echo -e "${GREEN}Published ai-framework ${VERSION} to PyPI!${NC}"
