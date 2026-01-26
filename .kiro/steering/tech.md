# Tech Stack

## Language & Runtime

- Python 3.12+
- Async/await patterns throughout (asyncio)

## Build System

- **Package Manager**: uv (Astral)
- **Build Backend**: hatchling
- **Project Config**: pyproject.toml

## Key Dependencies

- `mcp[cli]` - Model Context Protocol server framework (FastMCP)
- `psycopg[binary]` + `psycopg-pool` - PostgreSQL async driver with connection pooling
- `pglast` - PostgreSQL query parser
- `instructor` - LLM integration for AI-powered analysis
- `pydantic` - Data validation and settings
- `attrs` - Data classes
- `humanize` - Human-readable formatting

## Development Tools

- `ruff` - Linting and formatting (line-length: 150)
- `pyright` - Type checking (standard mode)
- `pytest` + `pytest-asyncio` - Testing
- `pre-commit` - Git hooks for quality checks
- `docker` - Container testing

## Common Commands

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run pre-commit run --all-files

# Format code
uv run ruff format

# Type check
uv run pyright

# Build package
uv build

# Start server (stdio mode)
./start.sh

# Start server (SSE mode for web)
./start.sh --transport sse --sse-port 8099

# Start in restricted/read-only mode
./start.sh --access-mode restricted
```

## Code Style

- Line length: 150 characters
- Quote style: double quotes
- Import style: single-line imports, sorted
- Naming: PEP8 conventions
- Type hints: Required for function signatures
