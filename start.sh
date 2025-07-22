#!/bin/bash

# PostgreSQL MCP Pro Plus Start Script
# Supports flexible configuration via command line arguments

# Load environment variables if .env exists
if [[ -f .env ]]; then
	source .env
fi

# Default values
DEFAULT_TRANSPORT="stdio"
DEFAULT_ACCESS_MODE="unrestricted"
DEFAULT_SSE_HOST="localhost"
DEFAULT_SSE_PORT="8000"

# Parse command line arguments
ACCESS_MODE="$DEFAULT_ACCESS_MODE"
TRANSPORT="$DEFAULT_TRANSPORT"
SSE_HOST="$DEFAULT_SSE_HOST"
SSE_PORT="$DEFAULT_SSE_PORT"

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "PostgreSQL MCP Pro Plus - Advanced Database Analysis & Optimization Suite"
    echo ""
    echo "OPTIONS:"
    echo "  --access-mode MODE      Set access mode: 'unrestricted' or 'restricted' (default: unrestricted)"
    echo "  --transport TYPE        Transport type: 'stdio' or 'sse' (default: stdio)"
    echo "  --sse-host HOST         SSE server host (default: localhost)"
    echo "  --sse-port PORT         SSE server port (default: 8000)"
    echo "  --help, -h              Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0                                    # Start with default settings (stdio, unrestricted)"
    echo "  $0 --access-mode restricted           # Start in read-only mode"
    echo "  $0 --transport sse --sse-port 8099    # Start SSE server on port 8099"
    echo "  $0 --transport sse --sse-host 0.0.0.0 --sse-port 8099  # SSE server accessible externally"
    echo ""
    echo "ENVIRONMENT:"
    echo "  DATABASE_URI            PostgreSQL connection string (required)"
    echo "                          Format: postgresql://user:pass@host:port/dbname"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --access-mode)
            ACCESS_MODE="$2"
            if [[ "$ACCESS_MODE" != "restricted" && "$ACCESS_MODE" != "unrestricted" ]]; then
                echo "Error: access-mode must be 'restricted' or 'unrestricted'"
                exit 1
            fi
            shift 2
            ;;
        --transport)
            TRANSPORT="$2"
            if [[ "$TRANSPORT" != "stdio" && "$TRANSPORT" != "sse" ]]; then
                echo "Error: transport must be 'stdio' or 'sse'"
                exit 1
            fi
            shift 2
            ;;
        --sse-host)
            SSE_HOST="$2"
            shift 2
            ;;
        --sse-port)
            SSE_PORT="$2"
            if ! [[ "$SSE_PORT" =~ ^[0-9]+$ ]] || [ "$SSE_PORT" -lt 1 ] || [ "$SSE_PORT" -gt 65535 ]; then
                echo "Error: sse-port must be a valid port number (1-65535)"
                exit 1
            fi
            shift 2
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check for required DATABASE_URI
if [[ -z "${DATABASE_URI:-${DATABASE_URL}}" ]]; then
    echo "Error: DATABASE_URI environment variable is required"
    echo ""
    echo "Please set DATABASE_URI in your .env file or environment:"
    echo "  DATABASE_URI=postgresql://username:password@localhost:5432/database_name"
    echo ""
    echo "Or create a .env file with:"
    echo "  echo 'DATABASE_URI=postgresql://username:password@localhost:5432/database_name' > .env"
    exit 1
fi

# Build command arguments
CMD_ARGS=("${DATABASE_URI:-${DATABASE_URL}}")
CMD_ARGS+=("--access-mode" "$ACCESS_MODE")
CMD_ARGS+=("--transport" "$TRANSPORT")

if [[ "$TRANSPORT" == "sse" ]]; then
    CMD_ARGS+=("--sse-host" "$SSE_HOST")
    CMD_ARGS+=("--sse-port" "$SSE_PORT")
fi

# Display startup information
echo "🚀 Starting PostgreSQL MCP Pro Plus..."
echo "   Access Mode: $ACCESS_MODE"
echo "   Transport: $TRANSPORT"
if [[ "$TRANSPORT" == "sse" ]]; then
    echo "   SSE Host: $SSE_HOST"
    echo "   SSE Port: $SSE_PORT"
    echo "   Server URL: http://$SSE_HOST:$SSE_PORT"
fi
echo ""

# Start the server
exec postgres-mcp "${CMD_ARGS[@]}"
