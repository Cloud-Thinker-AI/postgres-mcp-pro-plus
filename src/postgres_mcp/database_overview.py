"""Database overview tool for comprehensive database analysis.

Extended from the original postgres-mcp project:
https://github.com/crystaldba/postgres-mcp
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class DatabaseOverviewTool:
    """Tool for generating comprehensive database overview with performance and security analysis."""

    def __init__(self, sql_driver):
        self.sql_driver = sql_driver
        self.max_tables_per_schema = 100  # Limit tables per schema
        self.enable_sampling = True  # Use sampling for large datasets
        self.timeout_seconds = 300  # 5 minute timeout

    async def get_database_overview(self, max_tables: int = 500, sampling_mode: bool = True, timeout: int = 300) -> dict[str, Any]:
        """Get comprehensive database overview with performance and security analysis.

        Args:
            max_tables: Maximum number of tables to analyze per schema (default: 500)
            sampling_mode: Use statistical sampling for large datasets (default: True)
            timeout: Maximum execution time in seconds (default: 300)
        """
        start_time = time.time()
        try:
            # Add timeout wrapper
            return await asyncio.wait_for(
                self._get_database_overview_internal(max_tables, sampling_mode, start_time),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Database overview timed out after {timeout} seconds")
            return {
                "error": f"Operation timed out after {timeout} seconds",
                "execution_metadata": {
                    "max_tables": max_tables,
                    "sampling_mode": sampling_mode,
                    "timeout": timeout,
                    "execution_time": time.time() - start_time
                }
            }
        except Exception as e:
            logger.error(f"Error generating database overview: {e!s}")
            return {
                "error": str(e),
                "execution_metadata": {
                    "max_tables": max_tables,
                    "sampling_mode": sampling_mode,
                    "timeout": timeout,
                    "execution_time": time.time() - start_time
                }
            }

    async def _get_database_overview_internal(self, max_tables: int, sampling_mode: bool, start_time: float) -> dict[str, Any]:
        """Internal implementation of database overview."""
        try:
            db_info = {
                "schemas": {},
                "database_summary": {
                    "total_schemas": 0,
                    "total_tables": 0,
                    "total_size_bytes": 0,
                    "total_rows": 0,
                },
                "performance_overview": {},
                "security_overview": {},
                "relationships": {"foreign_keys": [], "relationship_summary": {}},
                "execution_metadata": {
                    "max_tables": max_tables,
                    "sampling_mode": sampling_mode,
                    "timeout": self.timeout_seconds,
                    "tables_analyzed": 0,
                    "tables_skipped": 0
                }
            }

            # Get database-wide performance metrics
            await self._get_performance_metrics(db_info)

            # Get schema information
            user_schemas = await self._get_user_schemas()
            db_info["database_summary"]["total_schemas"] = len(user_schemas)

            # Track relationships and table stats
            all_relationships = []
            table_connections = {}
            all_tables_with_stats = []

            # Process each schema with limits
            for schema in user_schemas:
                logger.info(f"Processing schema: {schema}")
                schema_info = await self._process_schema(
                    schema, all_relationships, table_connections, all_tables_with_stats, max_tables, sampling_mode
                )
                db_info["schemas"][schema] = schema_info

                # Update database totals
                db_info["database_summary"]["total_tables"] += schema_info["table_count"]
                db_info["database_summary"]["total_size_bytes"] += schema_info["total_size_bytes"]
                db_info["database_summary"]["total_rows"] += schema_info["total_rows"]

                # Update metadata
                db_info["execution_metadata"]["tables_analyzed"] += schema_info.get("tables_analyzed", 0)
                db_info["execution_metadata"]["tables_skipped"] += schema_info.get("tables_skipped", 0)

            # Add human-readable database size
            total_size_gb = db_info["database_summary"]["total_size_bytes"] / (1024**3)
            db_info["database_summary"]["total_size_readable"] = f"{total_size_gb:.2f} GB"

            # Add top tables summary
            if all_tables_with_stats:
                await self._add_top_tables_summary(db_info, all_tables_with_stats)

            # Add security overview
            await self._get_security_overview(db_info)

            # Build relationship summary
            await self._build_relationship_summary(
                db_info, all_relationships, table_connections, user_schemas
            )

            # Add execution timing
            execution_time = time.time() - start_time
            db_info["execution_metadata"]["execution_time"] = round(execution_time, 2)
            logger.info(
                f"Database overview complete: {db_info['database_summary']['total_tables']} tables "
                f"across {len(user_schemas)} schemas, {len(all_relationships)} relationships "
                f"in {execution_time:.2f}s"
            )
            return db_info

        except Exception as e:
            logger.error(f"Error generating database overview: {e!s}")
            return {"error": str(e)}

    async def _get_user_schemas(self) -> list[str]:
        """Get list of user schemas (excluding system schemas)."""
        query = """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            AND schema_name NOT LIKE 'pg_temp_%'
            AND schema_name NOT LIKE 'pg_toast_temp_%'
            ORDER BY schema_name
        """
        rows = await self.sql_driver.execute_query(query)
        return [row.cells["schema_name"] for row in rows] if rows else []

    async def _get_performance_metrics(self, db_info: dict[str, Any]) -> None:
        """Get database-wide performance metrics."""
        db_stats_query = """
            SELECT
                pg_database_size(current_database()) as database_size_bytes,
                (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                (SELECT count(*) FROM pg_stat_activity) as total_connections,
                current_setting('max_connections')::int as max_connections
        """

        rows = await self.sql_driver.execute_query(db_stats_query)
        if rows and rows[0]:
            row = rows[0].cells
            db_info["performance_overview"] = {
                "active_connections": row["active_connections"],
                "total_connections": row["total_connections"],
                "max_connections": row["max_connections"],
                "connection_usage_percent": round(
                    (row["total_connections"] / row["max_connections"]) * 100, 2
                ) if row["max_connections"] > 0 else 0,
            }

    async def _process_schema(
        self,
        schema: str,
        all_relationships: list[dict[str, Any]],
        table_connections: dict[str, int],
        all_tables_with_stats: list[dict[str, Any]],
        max_tables: int,
        sampling_mode: bool,
    ) -> dict[str, Any]:
        """Process a single schema and return its information."""
        # Get tables in schema
        tables = await self._get_tables_in_schema(schema)

        # Apply sampling and limits
        tables_to_process = tables
        tables_skipped = 0

        if len(tables) > max_tables:
            if sampling_mode:
                # Sample tables evenly across the list
                step = len(tables) / max_tables
                tables_to_process = [tables[int(i * step)] for i in range(max_tables)]
                tables_skipped = len(tables) - max_tables
                logger.info(f"Schema {schema}: sampling {max_tables} of {len(tables)} tables")
            else:
                # Take first N tables
                tables_to_process = tables[:max_tables]
                tables_skipped = len(tables) - max_tables
                logger.info(f"Schema {schema}: limiting to first {max_tables} of {len(tables)} tables")

        schema_info = {
            "table_count": len(tables),
            "total_size_bytes": 0,
            "total_rows": 0,
            "tables": {},
            "tables_analyzed": len(tables_to_process),
            "tables_skipped": tables_skipped,
            "is_sampled": tables_skipped > 0
        }

        # Get bulk table statistics
        bulk_stats = await self._get_bulk_table_stats(tables_to_process, schema)
        for table in tables_to_process:
            # Get table stats from bulk query
            table_stats = bulk_stats.get(table, {"row_count": 0, "size_bytes": 0})

            # Get foreign key relationships (keep individual for now due to complexity)
            relationships = await self._get_foreign_keys(table, schema)
            for relationship in relationships:
                all_relationships.append(relationship)

                # Track connections
                from_key = f"{schema}.{table}"
                to_key = f"{relationship['to_schema']}.{relationship['to_table']}"
                table_connections[from_key] = table_connections.get(from_key, 0) + 1
                table_connections[to_key] = table_connections.get(to_key, 0) + 1

            if "error" not in table_stats:
                essential_info = {
                    "row_count": table_stats.get("row_count", 0),
                    "size_bytes": table_stats.get("size_bytes", 0),
                    "size_readable": self._format_bytes(table_stats.get("size_bytes", 0)),
                    "needs_attention": [],
                }

                # Add performance insights
                if table_stats.get("seq_scans", 0) > table_stats.get("idx_scans", 0):
                    essential_info["needs_attention"].append("frequent_seq_scans")
                if essential_info["row_count"] == 0:
                    essential_info["needs_attention"].append("empty_table")

                # Store for analysis
                all_tables_with_stats.append({
                    "schema": schema,
                    "table": table,
                    "size_bytes": essential_info["size_bytes"],
                    "total_scans": table_stats.get("seq_scans", 0) + table_stats.get("idx_scans", 0),
                })

                schema_info["tables"][table] = essential_info
                schema_info["total_size_bytes"] += essential_info["size_bytes"]
                schema_info["total_rows"] += essential_info["row_count"]
            else:
                schema_info["tables"][table] = {"error": "stats_unavailable"}

        return schema_info

    async def _get_tables_in_schema(self, schema: str) -> list[str]:
        """Get list of tables in a schema."""
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        rows = await self.sql_driver.execute_query(query, (schema,))
        return [row.cells["table_name"] for row in rows] if rows else []

    async def _get_bulk_table_stats(self, tables: list[str], schema: str) -> dict[str, dict[str, Any]]:
        """Get table statistics for multiple tables in a single query."""
        if not tables:
            return {}

        # Create IN clause for tables
        table_placeholders = ','.join(['%s'] * len(tables))
        query = f"""
            SELECT
                relname as table_name,
                COALESCE(n_tup_ins + n_tup_upd + n_tup_del, 0) as total_modifications,
                COALESCE(n_tup_ins, 0) as inserts,
                COALESCE(n_tup_upd, 0) as updates,
                COALESCE(n_tup_del, 0) as deletes,
                COALESCE(seq_scan, 0) as seq_scans,
                COALESCE(seq_tup_read, 0) as seq_tup_read,
                COALESCE(idx_scan, 0) as idx_scans,
                COALESCE(idx_tup_fetch, 0) as idx_tup_fetch,
                COALESCE(n_live_tup, 0) as live_tuples,
                COALESCE(n_dead_tup, 0) as dead_tuples,
                pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(relname)) as size_bytes,
                COALESCE(n_live_tup, 0) as row_count
            FROM pg_stat_user_tables
            WHERE schemaname = %s AND relname IN ({table_placeholders})
        """

        try:
            params = [schema, *tables]
            rows = await self.sql_driver.execute_query(query, params)

            result = {}
            if rows:
                for row in rows:
                    table_name = row.cells["table_name"]
                    result[table_name] = dict(row.cells)

            # Add empty stats for tables not found in pg_stat_user_tables
            for table in tables:
                if table not in result:
                    result[table] = {"row_count": 0, "size_bytes": 0}

            return result
        except Exception as e:
            logger.warning(f"Could not get bulk stats for schema {schema}: {e}")
            # Fallback to individual queries
            result = {}
            for table in tables:
                result[table] = await self._get_table_stats(table, schema)
            return result

    async def _get_foreign_keys(self, table: str, schema: str) -> list[dict[str, Any]]:
        """Get foreign key relationships for a table."""
        query = """
            SELECT
                tc.constraint_name,
                tc.table_schema as from_schema,
                tc.table_name as from_table,
                string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) as from_columns,
                ccu.table_schema as to_schema,
                ccu.table_name as to_table,
                string_agg(ccu.column_name, ',' ORDER BY kcu.ordinal_position) as to_columns
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
            GROUP BY tc.constraint_name, tc.table_schema, tc.table_name,
                     ccu.table_schema, ccu.table_name
        """

        relationships = []
        try:
            rows = await self.sql_driver.execute_query(query, (schema, table))
            for row in rows:
                relationship = {
                    "from_schema": row.cells["from_schema"],
                    "from_table": row.cells["from_table"],
                    "from_columns": row.cells["from_columns"].split(","),
                    "to_schema": row.cells["to_schema"],
                    "to_table": row.cells["to_table"],
                    "to_columns": row.cells["to_columns"].split(","),
                    "constraint_name": row.cells["constraint_name"],
                }
                relationships.append(relationship)
        except Exception as e:
            logger.warning(f"Could not get foreign keys for {schema}.{table}: {e}")

        return relationships

    async def _get_table_stats(self, table: str, schema: str) -> dict[str, Any]:
        """Get basic table statistics."""
        try:
            stats_query = """
                SELECT
                    COALESCE(n_tup_ins + n_tup_upd + n_tup_del, 0) as total_modifications,
                    COALESCE(n_tup_ins, 0) as inserts,
                    COALESCE(n_tup_upd, 0) as updates,
                    COALESCE(n_tup_del, 0) as deletes,
                    COALESCE(seq_scan, 0) as seq_scans,
                    COALESCE(seq_tup_read, 0) as seq_tup_read,
                    COALESCE(idx_scan, 0) as idx_scans,
                    COALESCE(idx_tup_fetch, 0) as idx_tup_fetch,
                    COALESCE(n_live_tup, 0) as live_tuples,
                    COALESCE(n_dead_tup, 0) as dead_tuples,
                    pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(relname)) as size_bytes,
                    COALESCE(n_live_tup, 0) as row_count
                FROM pg_stat_user_tables
                WHERE schemaname = %s AND relname = %s
            """

            rows = await self.sql_driver.execute_query(stats_query, (schema, table))
            if rows and rows[0]:
                return dict(rows[0].cells)
            else:
                # Fallback for tables without stats
                return {"row_count": 0, "size_bytes": 0}
        except Exception as e:
            logger.warning(f"Could not get stats for {schema}.{table}: {e}")
            return {"error": str(e)}

    async def _add_top_tables_summary(
        self, db_info: dict[str, Any], all_tables_with_stats: list[dict[str, Any]]
    ) -> None:
        """Add top tables summary for performance insights."""
        # Top 5 tables by size
        top_by_size = sorted(all_tables_with_stats, key=lambda x: x["size_bytes"], reverse=True)[:5]
        # Top 5 most active tables
        top_by_activity = sorted(all_tables_with_stats, key=lambda x: x["total_scans"], reverse=True)[:5]

        db_info["performance_overview"]["top_tables"] = {
            "largest": [
                {
                    "schema": t["schema"],
                    "table": t["table"],
                    "size_bytes": t["size_bytes"],
                    "size_readable": self._format_bytes(t["size_bytes"]),
                }
                for t in top_by_size
            ],
            "most_active": [
                {
                    "schema": t["schema"],
                    "table": t["table"],
                    "total_scans": t["total_scans"],
                }
                for t in top_by_activity
            ],
        }

    async def _get_security_overview(self, db_info: dict[str, Any]) -> None:
        """Get security overview and recommendations."""
        security_issues = []
        security_score = 100

        # Check security settings
        security_settings = {}
        settings_to_check = ["ssl", "log_connections", "password_encryption"]

        for setting in settings_to_check:
            try:
                result = await self.sql_driver.execute_query(f"SHOW {setting}")
                security_settings[setting] = result[0].cells[setting] if result and result[0] else "unknown"
            except Exception:
                security_settings[setting] = "not available"

        # Check for pg_stat_statements extension
        ext_query = "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements')"
        ext_result = await self.sql_driver.execute_query(ext_query)
        pg_stat_statements_installed = (
            ext_result[0].cells["exists"] if ext_result and ext_result[0] else False
        )
        security_settings["pg_stat_statements_installed"] = pg_stat_statements_installed

        # Security issue detection
        if security_settings.get("ssl") != "on":
            security_issues.append("ssl_disabled")
            security_score -= 20

        if not pg_stat_statements_installed:
            security_issues.append("no_query_monitoring")
            security_score -= 10

        # Get user security summary
        users_query = """
            SELECT
                COUNT(*) as total_users,
                COUNT(*) FILTER (WHERE rolsuper = true) as superusers,
                COUNT(*) FILTER (WHERE rolconnlimit = -1) as unlimited_connections
            FROM pg_roles
            WHERE rolcanlogin = true
        """

        user_result = await self.sql_driver.execute_query(users_query)
        if user_result and user_result[0]:
            user_stats = user_result[0].cells
            total_users = user_stats["total_users"]
            superusers = user_stats["superusers"]
            unlimited_conn = user_stats["unlimited_connections"]

            if superusers > 1:
                security_issues.append("multiple_superusers")
                security_score -= 15

            if unlimited_conn > 0:
                security_issues.append("unlimited_connections")
                security_score -= 10

            recommendations = []
            if "ssl_disabled" in security_issues:
                recommendations.append("Enable SSL encryption")
            if "no_query_monitoring" in security_issues:
                recommendations.append("Install pg_stat_statements for query monitoring")
            if "multiple_superusers" in security_issues:
                recommendations.append("Review superuser privileges")
            if "unlimited_connections" in security_issues:
                recommendations.append("Set connection limits for users")

            db_info["security_overview"] = {
                "security_score": max(0, security_score),
                "total_users": total_users,
                "superusers": superusers,
                "unlimited_connections": unlimited_conn,
                "security_settings": security_settings,
                "security_issues": security_issues,
                "recommendations": recommendations,
            }

    async def _build_relationship_summary(
        self,
        db_info: dict[str, Any],
        all_relationships: list[dict[str, Any]],
        table_connections: dict[str, int],
        user_schemas: list[str],
    ) -> None:
        """Build relationship summary and insights."""
        db_info["relationships"]["foreign_keys"] = all_relationships

        if all_relationships:
            # Find most connected tables
            most_connected = sorted(table_connections.items(), key=lambda x: x[1], reverse=True)[:5]

            # Find isolated tables
            all_table_keys = set()
            for schema in user_schemas:
                tables = await self._get_tables_in_schema(schema)
                for table in tables:
                    all_table_keys.add(f"{schema}.{table}")

            connected_tables = set(table_connections.keys())
            isolated_tables = all_table_keys - connected_tables

            # Find hub tables (highly referenced)
            relationship_patterns = {}
            for rel in all_relationships:
                to_table = f"{rel['to_schema']}.{rel['to_table']}"
                relationship_patterns[to_table] = relationship_patterns.get(to_table, 0) + 1

            hub_tables = sorted(
                relationship_patterns.items(), key=lambda x: x[1], reverse=True
            )[:5]

            insights = []
            if len(isolated_tables) > 0:
                insights.append(f"{len(isolated_tables)} tables have no foreign key relationships")
            if hub_tables:
                top_hub = hub_tables[0]
                insights.append(f"{top_hub[0]} is the most referenced table ({top_hub[1]} references)")

            db_info["relationships"]["relationship_summary"] = {
                "total_relationships": len(all_relationships),
                "connected_tables": len(connected_tables),
                "isolated_tables": len(isolated_tables),
                "most_connected_tables": [
                    {"table": table, "connections": count} for table, count in most_connected
                ],
                "hub_tables": [
                    {"table": table, "referenced_by": count} for table, count in hub_tables
                ],
                "relationship_insights": insights,
            }
        else:
            db_info["relationships"]["relationship_summary"] = {
                "total_relationships": 0,
                "connected_tables": 0,
                "isolated_tables": db_info["database_summary"]["total_tables"],
                "relationship_insights": ["No foreign key relationships found in the database"],
            }

    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human-readable string."""
        if bytes_value == 0:
            return "0 B"

        value = float(bytes_value)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if value < 1024.0:
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} PB"
