#!/bin/bash

# Load environment variables if .env exists
if [ -f .env ]; then
    source .env
fi

# Start the server using the postgres-mcp command
postgres-mcp ${DATABASE_URI:-$DATABASE_URL} --transport sse --sse-port 8099
