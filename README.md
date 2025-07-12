# Postgres MCP Pro Plus

<p align="center">
<strong>Extended version based on <a href="https://github.com/crystaldba/postgres-mcp">crystaldba/postgres-mcp</a></strong>
</p>

## Available Tools

| Tool Name | Description |
|-----------|-------------|
| `list_schemas` | List all schemas in the database with their owners and types |
| `list_objects` | List database objects (tables, views, sequences, extensions) within a specified schema |
| `get_object_details` | Show detailed information about a specific database object including columns, constraints, and indexes |
| `execute_sql` | Execute SQL statements on the database (read-only in restricted mode, full access in unrestricted mode) |
| `explain_query` | Get the execution plan for a SQL query with cost estimates. Can simulate hypothetical indexes using HypoPG extension |
| `get_top_queries` | Report the slowest or most resource-intensive queries using pg_stat_statements data |
| `analyze_workload_indexes` | Analyze frequently executed queries and recommend optimal indexes using DTA or LLM methods |
| `analyze_query_indexes` | Analyze a list of specific SQL queries (up to 10) and recommend optimal indexes |
| `analyze_db_health` | Perform comprehensive health checks including buffer cache, connections, vacuum, sequences, replication, and constraints |

## Extended Tools

| Tool Name | Description |
|-----------|-------------|
| `get_database_overview` | Get comprehensive database overview with performance and security analysis |

### Database Overview Tool Details

The `get_database_overview` tool provides a comprehensive analysis of your PostgreSQL database including:

- **Schema Analysis**: Complete schema structure with table relationships
- **Performance Metrics**: Query performance, index usage, and resource utilization
- **Security Analysis**: User permissions, role assignments, and security configurations
- **Storage Analysis**: Table sizes, index efficiency, and disk usage patterns
- **Health Indicators**: Connection status, vacuum statistics, and system health

**Parameters:**
- `max_tables` (default: 500): Maximum number of tables to analyze per schema
- `sampling_mode` (default: true): Use statistical sampling for large datasets
- `timeout` (default: 300): Maximum execution time in seconds

## Basic Usage

### Setup

1. Create a `.env` file in the project root:
```bash
DATABASE_URI=postgresql://username:password@localhost:5432/database_name
```

2. Run the startup script:
```bash
./start.sh
```

The server will start in unrestricted mode by default. For read-only access, use:
```bash
./start.sh --access-mode restricted
```

## License

MIT License
