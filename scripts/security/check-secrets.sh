#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Scanning repository for potential secrets...${NC}"

# Run detect-secrets to find potential secrets
detect-secrets scan --baseline .secrets.baseline

# Check if any secrets were found
if [ $? -eq 0 ]; then
    echo -e "${GREEN}No new secrets detected in code.${NC}"
else
    echo -e "${RED}Potential secrets detected in your code!${NC}"
    echo -e "${YELLOW}Please review the output above and fix any issues.${NC}"
    echo -e "${YELLOW}If these are false positives, update the baseline with:${NC}"
    echo -e "${YELLOW}detect-secrets scan --baseline .secrets.baseline${NC}"
fi
