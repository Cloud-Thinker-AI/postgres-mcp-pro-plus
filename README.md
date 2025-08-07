# Postgres MCP Pro Plus

<p align="center">
<strong>Advanced PostgreSQL Database Analysis & Optimization Suite</strong><br>
<em>Extended version based on <a href="https://github.com/crystaldba/postgres-mcp">crystaldba/postgres-mcp</a></em>
</p>

## 🚀 Key Features

- **🔍 Comprehensive Database Analysis**: Deep insights into schema structure, relationships, and performance
- **⚡ AI-Powered Optimization**: Intelligent index recommendations using Database Tuning Advisor (DTA) and LLM methods
- **🩺 Advanced Health Monitoring**: Multi-dimensional health checks with predictive analytics
- **🔒 Lock & Blocking Analysis**: Real-time detection and resolution of query blocking and deadlocks
- **🧹 Smart Maintenance**: Automated vacuum analysis with bloat detection and maintenance scheduling
- **📊 Performance Intelligence**: Query performance analysis with resource usage optimization
- **🔐 Security Assessment**: Comprehensive security analysis and recommendations
- **🐳 Docker Ready**: Containerized deployment with Docker Compose support

## 📋 Available Tools

### Core Database Operations

| Tool Name            | Description                                                              |
| -------------------- | ------------------------------------------------------------------------ |
| `list_schemas`       | List all schemas with ownership and type classification                  |
| `list_objects`       | Browse database objects (tables, views, sequences, extensions) by schema |
| `get_object_details` | Detailed object analysis including columns, constraints, and indexes     |
| `execute_sql`        | Execute SQL with safety controls (restricted/unrestricted modes)         |

### Performance & Optimization

| Tool Name                  | Description                                                                |
| -------------------------- | -------------------------------------------------------------------------- |
| `explain_query`            | Advanced execution plan analysis with HypoPG hypothetical index simulation |
| `get_top_queries`          | Identify slow and resource-intensive queries with performance metrics      |
| `analyze_workload_indexes` | AI-powered index recommendations from workload analysis (DTA/LLM)          |
| `analyze_query_indexes`    | Targeted index optimization for specific query sets (up to 10 queries)     |

### Health & Monitoring

| Tool Name                     | Description                                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `analyze_db_health`           | Comprehensive health checks: indexes, connections, vacuum, sequences, replication, buffer cache, constraints |
| `get_blocking_queries`        | Advanced blocking analysis with lock hierarchy visualization and resolution recommendations                  |
| `analyze_vacuum_requirements` | Comprehensive vacuum analysis with bloat detection and maintenance recommendations                           |

### Advanced Analysis

| Tool Name                      | Description                                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------------ |
| `get_database_overview`        | Enterprise-grade database assessment with performance, security, and relationship analysis |
| `analyze_schema_relationships` | Schema dependency mapping with visual relationship analysis and coupling metrics           |

## 🔧 Tool Details & Capabilities

### 🔍 Database Overview Analysis

**Enterprise-grade comprehensive database assessment**

The `get_database_overview` tool provides multi-dimensional analysis:

- **📊 Schema Analysis**: Complete structure with table relationships and dependency mapping
- **⚡ Performance Metrics**: Query performance, index efficiency, and resource utilization patterns
- **🔐 Security Analysis**: User permissions, role assignments, and security configuration assessment
- **💾 Storage Analysis**: Table sizes, index bloat detection, and disk usage optimization
- **🩺 Health Indicators**: Connection health, vacuum statistics, and system performance metrics

**Configuration Options:**

- `max_tables` (default: 500): Maximum tables to analyze per schema for performance control
- `sampling_mode` (default: true): Statistical sampling for large datasets to optimize execution time
- `timeout` (default: 300): Maximum execution time with graceful timeout handling

### 🔒 Advanced Blocking Queries Analysis

**Real-time lock contention detection and resolution**

The `get_blocking_queries` tool features enterprise-grade capabilities:

**🎯 Core Features:**

- **Modern Detection**: Uses PostgreSQL's `pg_blocking_pids()` function for accurate blocking identification
- **Lock Hierarchy Visualization**: Complete blocking chains and process relationships
- **Comprehensive Metrics**: Process details, wait events, timing, lock types, and affected relations
- **Intelligent Recommendations**: Severity-based suggestions with specific optimization guidance
- **Production Ready**: Designed for enterprise database monitoring and performance troubleshooting

**📋 Analysis Output:**

- **Process Information**: PID, user, application name, client address, and connection details
- **Query Context**: Full query text, execution timing, and resource consumption
- **Lock Details**: Lock types, modes, affected database objects, and wait events
- **State Analysis**: Process states, wait information, and blocking duration
- **Trend Analysis**: Summary statistics and pattern recognition
- **Categorized Recommendations**: 🚨 Critical, ⚠️ Warning, 💡 Optimization, 🎯 Hotspot alerts

**🔧 PostgreSQL Compatibility:**

- **Minimum**: PostgreSQL 9.6+ (requires `pg_blocking_pids()` function)
- **Recommended**: PostgreSQL 12+ (enhanced lock monitoring features)
- **Optimal**: PostgreSQL 14+ (includes `pg_locks.waitstart` for precise wait timing)

### 🧹 Vacuum Analysis & Maintenance

**Comprehensive maintenance planning with bloat detection**

The `analyze_vacuum_requirements` tool provides:

- **📈 Bloat Analysis**: Table and index bloat detection with severity assessment
- **⚙️ Autovacuum Configuration**: Settings analysis and optimization recommendations
- **📊 Performance Impact**: Vacuum operation performance analysis and bottleneck identification
- **🗓️ Maintenance Planning**: Intelligent scheduling recommendations based on workload patterns
- **🚨 Critical Issue Detection**: Immediate attention alerts for maintenance-related problems
- **⚡ Configuration Optimization**: Tuning suggestions for vacuum parameters

### 🗺️ Schema Relationship Analysis

**Advanced dependency mapping and visualization**

The `analyze_schema_relationships` tool offers:

- **🔗 Dependency Mapping**: Complete inter-schema relationship visualization
- **📊 Coupling Analysis**: Schema coupling metrics and isolation scoring
- **🎯 Impact Assessment**: Change impact analysis for schema modifications
- **📈 Relationship Quality**: Foreign key relationship quality and consistency scoring
- **🔍 Pattern Detection**: Common anti-patterns and architectural recommendations

### ⚡ Index Optimization Intelligence

**AI-powered index recommendations with advanced algorithms**

**Database Tuning Advisor (DTA) Features:**

- **🧠 Pareto Optimization**: Multi-objective optimization balancing performance and storage
- **📊 Workload Analysis**: Pattern recognition from pg_stat_statements data
- **💰 Cost-Benefit Analysis**: Storage budget constraints with performance impact assessment
- **🎯 Query-Specific Tuning**: Targeted optimization for specific query sets
- **⏱️ Time-bounded Analysis**: Anytime algorithm with configurable runtime limits

**LLM-Powered Optimization:**

- **🤖 Intelligent Analysis**: Natural language understanding of query patterns
- **📝 Contextual Recommendations**: Human-readable explanations with implementation guidance
- **🔍 Advanced Pattern Recognition**: Complex query pattern detection and optimization

## 🚀 Quick Start

### Prerequisites

- PostgreSQL 9.6+ (PostgreSQL 12+ recommended, 14+ optimal)
- Python 3.8+
- Optional: HypoPG extension for hypothetical index analysis

### Installation & Setup

#### 1. Environment Configuration

Create a `.env` file in the project root:

```bash
DATABASE_URI=postgresql://username:password@localhost:5432/database_name
```

#### 2. Native Deployment

```bash
# Start the MCP server (default: stdio transport, unrestricted mode)
./start.sh

# Start in read-only mode for safer analysis
./start.sh --access-mode restricted

# Start with SSE transport for web integration
./start.sh --transport sse --sse-port 8099

# Start SSE server accessible externally
./start.sh --transport sse --sse-host 0.0.0.0 --sse-port 8099

# Show all available options
./start.sh --help
```

#### 3. Docker Deployment

```bash
# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f postgres-mcp
```

#### 4. Interactive Testing (MCP Inspector)

```bash
# Terminal 1: Start the MCP server with SSE transport
./start.sh --transport sse --sse-port 8099

# Terminal 2: Start the MCP Inspector (opens web interface)
./start-inspector.sh
```

The MCP Inspector provides:

- **Interactive Tool Testing**: Test all database analysis tools with a web UI
- **Parameter Exploration**: Discover tool capabilities and configuration options
- **Real-time Results**: View formatted analysis results in a user-friendly interface
- **Documentation**: Built-in tool documentation and usage examples

### 🔧 Access Modes

**Unrestricted Mode** (Default):

- Full SQL execution capabilities
- Database modification operations
- Complete administrative access

**Restricted Mode** (Recommended for analysis):

- Read-only operations with safety controls
- SQL injection protection
- Timeout enforcement (30s default)
- Safe for production analysis

### 📊 Usage Examples

#### Basic Server Operations

```bash
# Show help and configuration options
./start.sh --help

# Start with default settings (stdio, unrestricted)
./start.sh

# Start in production-safe mode
./start.sh --access-mode restricted

# Start web server for HTTP/SSE integration
./start.sh --transport sse --sse-port 8099
```

#### Health Check Examples

```bash
# Comprehensive health analysis (via MCP client)
analyze_db_health --health-type all

# Specific component checks
analyze_db_health --health-type index,vacuum,buffer

# Performance optimization workflow
get_top_queries --sort-by resources
analyze_workload_indexes --method dta --max-index-size-mb 1000
get_blocking_queries
```

## 🏗️ Architecture & Components

### Core Architecture

```
postgres-mcp/
├── 🔧 server.py              # MCP server & tool registration
├── 📊 database_health/       # Multi-dimensional health monitoring
├── ⚡ explain/               # Query execution plan analysis
├── 🎯 index/                 # AI-powered index optimization
├── 📈 top_queries/           # Performance query analysis
├── 🔒 blocking_queries.py    # Lock contention analysis
├── 🔍 database_overview.py   # Comprehensive assessment
├── 🗺️ schema_mapping.py      # Relationship visualization
├── 🧹 vacuum_analysis.py     # Maintenance optimization
└── 🛡️ sql/                   # SQL execution framework
```

### Database Health Components

- **Index Health**: Invalid, duplicate, bloated, and unused index detection
- **Connection Health**: Connection utilization and capacity analysis
- **Vacuum Health**: Transaction wraparound and maintenance monitoring
- **Sequence Health**: Sequence exhaustion and overflow protection
- **Replication Health**: Lag monitoring and slot management
- **Buffer Health**: Cache hit rate optimization for tables and indexes
- **Constraint Health**: Invalid constraint detection and remediation

### 🤖 AI Integration Features

**Database Tuning Advisor (DTA):**

- Pareto-optimal index selection algorithm
- Multi-query workload optimization
- Budget-constrained recommendation engine
- Time-bounded analysis with anytime approach

**LLM-Powered Analysis:**

- Natural language query pattern understanding
- Contextual optimization recommendations
- Human-readable explanations and guidance
- Advanced pattern recognition capabilities

## 📈 Recent Enhancements

### Latest Features (Recent Commits)

- ✅ **Comprehensive Tool Analysis**: Detailed analysis document with improvement recommendations
- ✅ **Enhanced Readability**: Streamlined code formatting across all modules
- ✅ **Robust Error Handling**: Improved None value handling in vacuum analysis
- ✅ **Advanced Visualizations**: Enhanced blocking queries analysis with detailed recommendations
- ✅ **Human-Readable Outputs**: Refactored analysis tools for better text presentation
- ✅ **Schema Relationship Mapping**: New schema dependency analysis and visualization
- ✅ **Docker Integration**: Complete containerization with Docker Compose support
- ✅ **Vacuum Analysis Tool**: Comprehensive maintenance recommendations and bloat detection

### Architecture Improvements

- **Modular Design**: Enhanced component separation and reusability
- **Async Optimization**: Improved performance with better async patterns
- **Safety Framework**: Comprehensive SQL execution safety controls
- **Error Recovery**: Robust error handling and graceful degradation
- **Performance Scaling**: Optimized for large database analysis
- **Enhanced Startup Scripts**: Flexible configuration with comprehensive validation and help system

## 📚 Documentation & Development

### Advanced Documentation

- **[Database Tools Analysis](plan/database-tools-analysis.md)**: Comprehensive analysis of all tools with improvement recommendations
- **[Tool Improvements Roadmap](todos/tool_improvements.md)**: Priority-based enhancement roadmap _(if available)_
- **Technical Implementation**: Detailed code documentation and API references

### Extension Points

- **Custom Health Checks**: Add domain-specific health monitoring
- **Plugin Architecture**: Extend with custom analysis tools
- **Integration APIs**: Connect with external monitoring systems
- **Custom Visualizations**: Add specialized reporting and dashboards

## 🔒 Security & Best Practices

### Security Features

- **SQL Injection Protection**: Comprehensive input sanitization
- **Access Mode Controls**: Restricted/unrestricted operation modes
- **Timeout Enforcement**: Configurable query timeout protection
- **Parameter Validation**: Robust input validation and sanitization
- **Error Handling**: Secure error reporting without information leakage

### Production Guidelines

- Use **restricted mode** for production analysis
- Configure appropriate **timeout values** for large operations
- Monitor **resource usage** during analysis operations
- Implement **regular health checks** for proactive monitoring
- Review **security configurations** and user permissions regularly

## 📄 License

MIT License

---

<p align="center">
<strong>🚀 Postgres MCP Pro Plus - Advanced Database Intelligence</strong><br>
<em>Empowering database professionals with AI-driven insights and optimization</em>
</p>
