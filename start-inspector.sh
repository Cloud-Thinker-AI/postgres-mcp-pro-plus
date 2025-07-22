#!/bin/bash

# PostgreSQL MCP Pro Plus Inspector
# Interactive tool testing interface

echo "🔍 Starting MCP Inspector for PostgreSQL MCP Pro Plus..."
echo ""
echo "The MCP Inspector provides a web interface to:"
echo "  • Test all database analysis tools interactively"
echo "  • Explore tool capabilities and parameters"
echo "  • View formatted results in a user-friendly interface"
echo ""
echo "Make sure your postgres-mcp server is running in another terminal:"
echo "  ./start.sh --transport sse --sse-port 8099"
echo ""
echo "Inspector will open in your web browser..."
echo ""

# Start Inspector
npx @modelcontextprotocol/inspector
