#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$(git rev-parse --show-toplevel)"

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

VERSION=$(grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')
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
