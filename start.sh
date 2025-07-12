#!/bin/bash

# Load environment variables
source .env

# Start the server
uv run postgres-mcp $DATABASE_URL --transport sse --sse-port 8099
