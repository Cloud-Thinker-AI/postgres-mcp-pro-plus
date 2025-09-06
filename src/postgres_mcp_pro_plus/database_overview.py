"""Database overview tool for comprehensive database analysis.

Extended from the original postgres-mcp project:
https://github.com/crystaldba/postgres-mcp
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .schema_mapping import SchemaMappingTool

logger = logging.getLogger(__name__)


class DatabaseOverviewTool:
    """Tool for generating comprehensive database overview with performance and security analysis."""

    def __init__(self, sql_driver):
        self.sql_driver = sql_driver
        self.max_tables_per_schema = 100  # Limit tables per schema
        self.enable_sampling = True  # Use sampling for large datasets
        self.timeout_seconds = 300  # 5 minute timeout
        self.schema_mapping_tool = SchemaMappingTool(sql_driver)

    async def get_database_overview(self, max_tables: int = 500, sampling_mode: bool = True, timeout: int = 300):
        """Get comprehensive database overview with performance and security analysis.

        Args:
            max_tables: Maximum number of tables to analyze per schema (default: 500)
            sampling_mode: Use statistical sampling for large datasets (default: True)
            timeout: Maximum execution time in seconds (default: 300)
        """
        start_time = time.time()
        try:
            # Add timeout wrapper
            result = await asyncio.wait_for(self._get_database_overview_internal(max_tables, sampling_mode, start_time), timeout=timeout)
            return self._format_as_text(result)
        except asyncio.TimeoutError:
            logger.warning(f"Database overview timed out after {timeout} seconds")
            error_result = {
                "error": f"Operation timed out after {timeout} seconds",
                "execution_metadata": {
                    "max_tables": max_tables,
                    "sampling_mode": sampling_mode,
                    "timeout": timeout,
                    "execution_time": time.time() - start_time,
                },
            }
            return self._format_as_text(error_result)
        except Exception as e:
            logger.error(f"Error generating database overview: {e!s}")
            error_result = {
                "error": str(e),
                "execution_metadata": {
                    "max_tables": max_tables,
                    "sampling_mode": sampling_mode,
                    "timeout": timeout,
                    "execution_time": time.time() - start_time,
                },
            }
            return self._format_as_text(error_result)

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
                    "tables_skipped": 0,
                },
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
            await self._build_relationship_summary(db_info, all_relationships, table_connections, user_schemas)

            # Add schema relationship mapping
            await self._add_schema_relationship_mapping(db_info, user_schemas)

            # Add performance hotspot identification
            await self._identify_performance_hotspots(db_info, all_tables_with_stats)

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
                "connection_usage_percent": round((row["total_connections"] / row["max_connections"]) * 100, 2) if row["max_connections"] > 0 else 0,
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
            "is_sampled": tables_skipped > 0,
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
                all_tables_with_stats.append(
                    {
                        "schema": schema,
                        "table": table,
                        "size_bytes": essential_info["size_bytes"],
                        "total_scans": table_stats.get("seq_scans", 0) + table_stats.get("idx_scans", 0),
                    }
                )

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
        table_placeholders = ",".join(["%s"] * len(tables))
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

    async def _add_top_tables_summary(self, db_info: dict[str, Any], all_tables_with_stats: list[dict[str, Any]]) -> None:
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
        pg_stat_statements_installed = ext_result[0].cells["exists"] if ext_result and ext_result[0] else False
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

            hub_tables = sorted(relationship_patterns.items(), key=lambda x: x[1], reverse=True)[:5]

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
                "most_connected_tables": [{"table": table, "connections": count} for table, count in most_connected],
                "hub_tables": [{"table": table, "referenced_by": count} for table, count in hub_tables],
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
        """Format bytes into compact human-readable string (no spaces)."""
        if bytes_value == 0:
            return "0B"
        value = float(bytes_value)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if value < 1024.0:
                return f"{value:.1f}{unit}"
            value /= 1024.0
        return f"{value:.1f}PB"

    async def _identify_performance_hotspots(self, db_info: dict[str, Any], all_tables_with_stats: list[dict[str, Any]]) -> None:
        """Identify performance hotspots in the database."""
        try:
            logger.info("Identifying performance hotspots...")

            hotspots = {
                "high_scan_ratio_tables": [],
                "high_dead_tuple_tables": [],
                "large_tables_with_issues": [],
                "high_modification_tables": [],
                "tables_needing_maintenance": [],
                "summary": {"total_hotspots": 0, "critical_issues": 0, "warning_issues": 0},
            }

            for table_info in all_tables_with_stats:
                schema = table_info["schema"]
                table = table_info["table"]
                stats = table_info

                # Calculate derived metrics
                total_scans = stats.get("seq_scans", 0) + stats.get("idx_scans", 0)
                seq_scan_ratio = (stats.get("seq_scans", 0) / total_scans) if total_scans > 0 else 0
                dead_tuple_ratio = (
                    (stats.get("dead_tuples", 0) / (stats.get("live_tuples", 0) + stats.get("dead_tuples", 0)))
                    if (stats.get("live_tuples", 0) + stats.get("dead_tuples", 0)) > 0
                    else 0
                )
                size_mb = stats.get("size_bytes", 0) / (1024 * 1024)

                # Identify high sequential scan ratio tables (>50% seq scans on tables with >1000 scans)
                if seq_scan_ratio > 0.5 and total_scans > 1000:
                    hotspots["high_scan_ratio_tables"].append(
                        {
                            "qualified_name": f"{schema}.{table}",
                            "seq_scan_ratio": round(seq_scan_ratio * 100, 1),
                            "total_scans": total_scans,
                            "seq_scans": stats.get("seq_scans", 0),
                            "size_mb": round(size_mb, 2),
                            "severity": "HIGH" if seq_scan_ratio > 0.8 else "MEDIUM",
                        }
                    )

                # Identify tables with high dead tuple ratio (>20%)
                if dead_tuple_ratio > 0.2:
                    hotspots["high_dead_tuple_tables"].append(
                        {
                            "qualified_name": f"{schema}.{table}",
                            "dead_tuple_ratio": round(dead_tuple_ratio * 100, 1),
                            "dead_tuples": stats.get("dead_tuples", 0),
                            "live_tuples": stats.get("live_tuples", 0),
                            "size_mb": round(size_mb, 2),
                            "severity": "HIGH" if dead_tuple_ratio > 0.4 else "MEDIUM",
                        }
                    )

                # Identify large tables with performance issues (>100MB with issues)
                if size_mb > 100:
                    issues = []
                    if seq_scan_ratio > 0.3:
                        issues.append(f"High seq scan ratio ({seq_scan_ratio * 100:.1f}%)")
                    if dead_tuple_ratio > 0.1:
                        issues.append(f"High dead tuple ratio ({dead_tuple_ratio * 100:.1f}%)")
                    if total_scans > 10000 and stats.get("idx_scans", 0) == 0:
                        issues.append("No index scans despite high activity")

                    if issues:
                        hotspots["large_tables_with_issues"].append(
                            {
                                "qualified_name": f"{schema}.{table}",
                                "size_mb": round(size_mb, 2),
                                "issues": issues,
                                "total_scans": total_scans,
                                "severity": "HIGH" if len(issues) > 1 else "MEDIUM",
                            }
                        )

                # Identify tables with high modification rates
                total_modifications = stats.get("total_modifications", 0)
                if total_modifications > 100000:  # Tables with >100k modifications
                    hotspots["high_modification_tables"].append(
                        {
                            "qualified_name": f"{schema}.{table}",
                            "total_modifications": total_modifications,
                            "inserts": stats.get("inserts", 0),
                            "updates": stats.get("updates", 0),
                            "deletes": stats.get("deletes", 0),
                            "size_mb": round(size_mb, 2),
                            "severity": "HIGH" if total_modifications > 1000000 else "MEDIUM",
                        }
                    )

                # Generate maintenance recommendations
                maintenance_needed = []
                if dead_tuple_ratio > 0.2:
                    maintenance_needed.append("VACUUM recommended")
                if dead_tuple_ratio > 0.4:
                    maintenance_needed.append("VACUUM FULL may be needed")
                if seq_scan_ratio > 0.5 and total_scans > 1000:
                    maintenance_needed.append("Consider adding indexes")
                if stats.get("n_mod_since_analyze", 0) > stats.get("live_tuples", 0) * 0.1:
                    maintenance_needed.append("ANALYZE recommended")

                if maintenance_needed:
                    hotspots["tables_needing_maintenance"].append(
                        {
                            "qualified_name": f"{schema}.{table}",
                            "recommendations": maintenance_needed,
                            "size_mb": round(size_mb, 2),
                            "priority": "HIGH" if len(maintenance_needed) > 1 else "MEDIUM",
                        }
                    )

            # Sort all hotspot lists by severity and size
            for hotspot_type in [
                "high_scan_ratio_tables",
                "high_dead_tuple_tables",
                "large_tables_with_issues",
                "high_modification_tables",
            ]:
                hotspots[hotspot_type] = sorted(hotspots[hotspot_type], key=lambda x: (x["severity"] == "HIGH", x.get("size_mb", 0)), reverse=True)[
                    :10
                ]  # Limit to top 10

            hotspots["tables_needing_maintenance"] = sorted(
                hotspots["tables_needing_maintenance"],
                key=lambda x: (x["priority"] == "HIGH", x.get("size_mb", 0)),
                reverse=True,
            )[:10]

            # Calculate summary statistics
            total_hotspots = sum(len(hotspots[key]) for key in hotspots if key != "summary")
            critical_issues = sum(
                1
                for hotspot_list in hotspots.values()
                if isinstance(hotspot_list, list)
                for item in hotspot_list
                if item.get("severity") == "HIGH" or item.get("priority") == "HIGH"
            )
            warning_issues = total_hotspots - critical_issues

            hotspots["summary"] = {
                "total_hotspots": total_hotspots,
                "critical_issues": critical_issues,
                "warning_issues": warning_issues,
            }

            db_info["performance_hotspots"] = hotspots
            logger.info(f"Performance hotspot analysis complete: {total_hotspots} hotspots identified")

        except Exception as e:
            logger.error(f"Error identifying performance hotspots: {e}")
            db_info["performance_hotspots"] = {"error": f"Failed to identify performance hotspots: {e!s}"}

    async def _add_schema_relationship_mapping(self, db_info: dict[str, Any], user_schemas: list[str]) -> None:
        """Add schema relationship mapping analysis to database overview."""
        try:
            logger.info("Analyzing schema relationships...")

            # Perform schema relationship analysis
            schema_mapping_results = await self.schema_mapping_tool.analyze_schema_relationships(user_schemas)

            # Add to database info (now returns text format)
            db_info["schema_relationship_mapping"] = {"analysis_text": schema_mapping_results}

            # Extract a simple count for logging (since we now get text, use a simpler approach)
            logger.info("Schema relationship mapping complete")

        except Exception as e:
            logger.error(f"Error adding schema relationship mapping: {e}")
            db_info["schema_relationship_mapping"] = {"error": f"Failed to analyze schema relationships: {e!s}"}

    def _format_as_text(self, result: dict[str, Any]) -> str:
        """Format database overview result as compact text (no emojis, minimal headers)."""
        if "error" in result:
            return f"Error: {result['error']}\nMeta: {self._format_execution_metadata(result.get('execution_metadata', {}))}"

        out: list[str] = []

        # Database summary (single line)
        db_summary = result.get("database_summary", {})
        out.append(
            "DB: "
            f"schemas={db_summary.get('total_schemas', 0)} "
            f"tables={db_summary.get('total_tables', 0)} "
            f"size={db_summary.get('total_size_readable', 'N/A')} "
            f"rows={db_summary.get('total_rows', 0)}"
        )

        # Performance Overview
        perf_overview = result.get("performance_overview", {})
        if perf_overview:
            out.append(
                "Perf: "
                f"active={perf_overview.get('active_connections', 0)} "
                f"total={perf_overview.get('total_connections', 0)} "
                f"max={perf_overview.get('max_connections', 0)} "
                f"usage={perf_overview.get('connection_usage_percent', 0)}%"
            )
            top_tables = perf_overview.get("top_tables", {})
            if top_tables.get("largest"):
                largest = [f"{t['schema']}.{t['table']} {t['size_readable']}" for t in top_tables["largest"][:3]]
                out.append("Largest: " + "; ".join(largest))
            if top_tables.get("most_active"):
                active = [f"{t['schema']}.{t['table']} scans={t['total_scans']}" for t in top_tables["most_active"][:3]]
                out.append("MostActive: " + "; ".join(active))

        # Security Overview
        security_overview = result.get("security_overview", {})
        if security_overview:
            out.append(
                "Security: "
                f"score={security_overview.get('security_score', 0)}/100 "
                f"users={security_overview.get('total_users', 0)} "
                f"su={security_overview.get('superusers', 0)} "
                f"unlim_conn={security_overview.get('unlimited_connections', 0)}"
            )
            security_issues = security_overview.get("security_issues", [])
            if security_issues:
                out.append("SecIssues: " + ", ".join(security_issues))
            recommendations = security_overview.get("recommendations", [])
            if recommendations:
                out.append("SecRecs: " + ", ".join(recommendations))

        # Performance Hotspots
        hotspots = result.get("performance_hotspots", {})
        if hotspots and "error" not in hotspots:
            summary = hotspots.get("summary", {})
            out.append(
                f"Hotspots: total={summary.get('total_hotspots', 0)} crit={summary.get('critical_issues', 0)} warn={summary.get('warning_issues', 0)}"
            )
            if hotspots.get("high_scan_ratio_tables"):
                items = [
                    f"{t['qualified_name']} r={t['seq_scan_ratio']}% sc={t['total_scans']} sz={t['size_mb']}MB sev={'H' if t['severity'] == 'HIGH' else 'M'}"
                    for t in hotspots["high_scan_ratio_tables"][:5]
                ]
                out.append("HighSeqScan: " + "; ".join(items))
            if hotspots.get("high_dead_tuple_tables"):
                items = [
                    f"{t['qualified_name']} dead={t['dead_tuple_ratio']}% sz={t['size_mb']}MB sev={'H' if t['severity'] == 'HIGH' else 'M'}"
                    for t in hotspots["high_dead_tuple_tables"][:5]
                ]
                out.append("HighDeadTuples: " + "; ".join(items))
            if hotspots.get("large_tables_with_issues"):
                items = [
                    f"{t['qualified_name']} sz={t['size_mb']}MB issues=[{', '.join(t.get('issues', []))}] sev={'H' if t['severity'] == 'HIGH' else 'M'}"
                    for t in hotspots["large_tables_with_issues"][:5]
                ]
                out.append("LargeWithIssues: " + "; ".join(items))
            if hotspots.get("high_modification_tables"):
                items = [f"{t['qualified_name']} mods={t['total_modifications']}" for t in hotspots["high_modification_tables"][:5]]
                out.append("HighMod: " + "; ".join(items))
            if hotspots.get("tables_needing_maintenance"):
                items = [
                    f"{t['qualified_name']} rec=[{', '.join(t.get('recommendations', []))}] prio={t.get('priority', 'MEDIUM')}"
                    for t in hotspots["tables_needing_maintenance"][:5]
                ]
                out.append("Maintenance: " + "; ".join(items))

        # Relationships Summary
        relationships = result.get("relationships", {})
        if relationships:
            rel_summary = relationships.get("relationship_summary", {})
            out.append(
                "Rel: "
                f"total={rel_summary.get('total_relationships', 0)} "
                f"connected={rel_summary.get('connected_tables', 0)} "
                f"isolated={rel_summary.get('isolated_tables', 0)}"
            )
            most_connected = rel_summary.get("most_connected_tables", [])
            if most_connected:
                out.append("MostConnected: " + "; ".join([f"{t['table']}({t['connections']})" for t in most_connected[:5]]))
            hub_tables = rel_summary.get("hub_tables", [])
            if hub_tables:
                out.append("Hubs: " + "; ".join([f"{t['table']}({t['referenced_by']})" for t in hub_tables[:5]]))
            insights = rel_summary.get("relationship_insights", [])
            if insights:
                out.append("RelInsights: " + "; ".join(insights))

        # Schema Details
        schemas = result.get("schemas", {})
        if schemas:
            for schema_name, schema_info in schemas.items():
                line = (
                    f"Schema {schema_name}: "
                    f"tables={schema_info.get('table_count', 0)} "
                    f"size={self._format_bytes(schema_info.get('total_size_bytes', 0))} "
                    f"rows={schema_info.get('total_rows', 0)}"
                )
                if schema_info.get("is_sampled"):
                    line += f" sampled={schema_info.get('tables_analyzed', 0)}/{schema_info.get('table_count', 0)}"
                out.append(line)

                tables = schema_info.get("tables", {})
                if tables:
                    top_schema_tables = sorted(
                        [(name, info) for name, info in tables.items() if "size_bytes" in info],
                        key=lambda x: x[1]["size_bytes"],
                        reverse=True,
                    )[:3]
                    if top_schema_tables:
                        tops = [f"{name} {info.get('size_readable', 'N/A')}" for name, info in top_schema_tables]
                        out.append("  Top: " + "; ".join(tops))

        # Schema Relationship Mapping
        schema_mapping = result.get("schema_relationship_mapping", {})
        if schema_mapping:
            if "error" in schema_mapping:
                out.append(f"SchemaMapError: {schema_mapping['error']}")
            elif "analysis_text" in schema_mapping:
                out.append("SchemaMap:")
                out.append(schema_mapping["analysis_text"])

        # Execution Metadata
        metadata = result.get("execution_metadata", {})
        if metadata:
            out.append("Meta: " + self._format_execution_metadata(metadata))

        return "\n".join(out)

    def _format_execution_metadata(self, metadata: dict[str, Any]) -> str:
        """Format execution metadata compactly on one line."""
        return (
            f"max_tables={metadata.get('max_tables', 'NA')} "
            f"sampling={metadata.get('sampling_mode', 'NA')} "
            f"timeout={metadata.get('timeout', 'NA')}s "
            f"analyzed={metadata.get('tables_analyzed', 0)} "
            f"skipped={metadata.get('tables_skipped', 0)} "
            f"time={metadata.get('execution_time', 'NA')}s"
        )
