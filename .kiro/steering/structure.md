# Project Structure

```
postgres-mcp-pro-plus/
├── src/postgres_mcp_pro_plus/     # Main package
│   ├── __init__.py                # Entry point, main() function
│   ├── server.py                  # MCP server, tool registration, CLI
│   ├── artifacts.py               # Response data structures
│   │
│   ├── sql/                       # Database connectivity layer
│   │   ├── sql_driver.py          # Connection pool, query execution
│   │   ├── safe_sql.py            # SafeSqlDriver with restrictions
│   │   ├── bind_params.py         # Parameter binding utilities
│   │   ├── extension_utils.py     # PostgreSQL extension helpers
│   │   └── index.py               # SQL module exports
│   │
│   ├── database_health/           # Health monitoring components
│   │   ├── database_health.py     # Main health tool orchestrator
│   │   ├── index_health_calc.py   # Index health checks
│   │   ├── connection_health_calc.py
│   │   ├── vacuum_health_calc.py
│   │   ├── sequence_health_calc.py
│   │   ├── replication_calc.py
│   │   ├── buffer_health_calc.py
│   │   └── constraint_health_calc.py
│   │
│   ├── explain/                   # Query plan analysis
│   │   └── explain_plan.py        # EXPLAIN tool with HypoPG support
│   │
│   ├── index/                     # Index optimization
│   │   ├── dta_calc.py            # Database Tuning Advisor algorithm
│   │   ├── llm_opt.py             # LLM-powered optimization
│   │   ├── index_opt_base.py      # Base classes
│   │   └── presentation.py        # Text output formatting
│   │
│   ├── top_queries/               # Query performance analysis
│   │   └── top_queries_calc.py    # pg_stat_statements analysis
│   │
│   ├── blocking_queries.py        # Lock contention analysis
│   ├── database_overview.py       # Comprehensive DB assessment
│   ├── schema_mapping.py          # Schema relationship analysis
│   └── vacuum_analysis.py         # Vacuum/bloat analysis
│
├── tests/
│   ├── conftest.py                # Pytest fixtures, Docker containers
│   ├── utils.py                   # Test utilities
│   ├── unit/                      # Unit tests (mocked)
│   └── integration/               # Integration tests (real DB)
│
├── scripts/security/              # Security scanning scripts
├── plan/                          # Analysis documentation
└── .kiro/
    ├── specs/                     # Feature specifications
    ├── steering/                  # AI guidance rules
    └── hooks/                     # Agent automation hooks
```

## Architecture Patterns

- **MCP Tools**: Registered via `@mcp.tool()` decorator in server.py
- **SQL Layer**: All DB access through SqlDriver/SafeSqlDriver
- **Health Checks**: Modular calculators in database_health/
- **Response Format**: Tools return `List[types.TextContent]` via `format_text_response()`

## Key Files

- `server.py` - All MCP tool definitions, CLI argument parsing
- `sql/sql_driver.py` - DbConnPool and SqlDriver classes
- `sql/safe_sql.py` - SafeSqlDriver with read-only enforcement
- `database_health/database_health.py` - Health check orchestration
