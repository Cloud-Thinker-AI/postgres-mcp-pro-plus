#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running Bandit security scan using Docker...${NC}"

# Bandit Docker image
BANDIT_IMAGE="ghcr.io/pycqa/bandit/bandit:latest"

# Target directories to scan (easy to add/remove folders)
TARGET_DIRS=(
    "src/postgres_mcp_pro_plus"
)

# Common directories to exclude from each target directory
EXCLUDE_PATTERNS=(
    "tests"
    ".venv"
    "__pycache__"
    ".ruff_cache"
    ".pytest_cache"
)

# Pull the latest bandit image if not present
if ! docker image inspect $BANDIT_IMAGE > /dev/null 2>&1; then
    echo -e "${YELLOW}Pulling Bandit Docker image...${NC}"
    docker pull $BANDIT_IMAGE
fi

# Build exclusion list for all target directories
EXCLUSIONS=""
for dir in "${TARGET_DIRS[@]}"; do
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
        if [ -n "$EXCLUSIONS" ]; then
            EXCLUSIONS="${EXCLUSIONS},${dir}/${pattern}"
        else
            EXCLUSIONS="${dir}/${pattern}"
        fi
    done
done

# Check which target directories actually exist
EXISTING_DIRS=()
for dir in "${TARGET_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        EXISTING_DIRS+=("$dir")
        echo -e "${YELLOW}  - Scanning: $dir${NC}"
    else
        echo -e "${YELLOW}  - Skipping: $dir (directory not found)${NC}"
    fi
done

# Exit if no directories to scan
if [ ${#EXISTING_DIRS[@]} -eq 0 ]; then
    echo -e "${RED}No target directories found to scan!${NC}"
    exit 1
fi

# Run bandit in Docker container
# Mount current directory as /app and run bandit against all target directories
# Using the same arguments as the original configuration: -ll (low and low), -r (recursive)
# Note: bandit is the entrypoint, so we don't need to specify it in the command
docker run --rm \
    -v "$(pwd):/app" \
    -w /app \
    $BANDIT_IMAGE \
    -ll -r "${EXISTING_DIRS[@]}" -x "$EXCLUSIONS"

# Capture exit code
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}Bandit security scan completed successfully - no issues found.${NC}"
else
    echo -e "${RED}Bandit security scan found potential security issues!${NC}"
    echo -e "${YELLOW}Please review the output above and fix any security concerns.${NC}"
fi

exit $exit_code
