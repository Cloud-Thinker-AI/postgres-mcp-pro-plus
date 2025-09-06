"""Schema relationship mapping module for PostgreSQL MCP server.

This module provides functionality to analyze and visualize inter-schema dependencies
and relationships in PostgreSQL databases.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SchemaNode:
    """Represents a schema node in the dependency graph."""

    name: str
    table_count: int = 0
    total_size_bytes: int = 0
    total_rows: int = 0
    outgoing_references: set[str] = field(default_factory=set)
    incoming_references: set[str] = field(default_factory=set)
    self_references: int = 0

    @property
    def dependency_score(self) -> float:
        """Calculate dependency score based on incoming and outgoing references."""
        return len(self.incoming_references) * 2 + len(self.outgoing_references)

    @property
    def isolation_score(self) -> float:
        """Calculate isolation score (lower is more isolated)."""
        return len(self.incoming_references) + len(self.outgoing_references)


@dataclass
class TableNode:
    """Represents a table node in the dependency graph."""

    schema: str
    name: str
    qualified_name: str
    size_bytes: int = 0
    row_count: int = 0
    outgoing_fks: list[str] = field(default_factory=list)
    incoming_fks: list[str] = field(default_factory=list)

    @property
    def connection_count(self) -> int:
        """Total number of connections (incoming + outgoing)."""
        return len(self.outgoing_fks) + len(self.incoming_fks)

    @property
    def is_hub(self) -> bool:
        """Check if table is a hub (has many incoming references)."""
        return len(self.incoming_fks) >= 3

    @property
    def is_isolated(self) -> bool:
        """Check if table has no foreign key relationships."""
        return len(self.outgoing_fks) == 0 and len(self.incoming_fks) == 0


class SchemaMappingTool:
    """Tool for analyzing and visualizing schema relationships and dependencies."""

    def __init__(self, sql_driver):
        self.sql_driver = sql_driver
        self.schema_nodes: dict[str, SchemaNode] = {}
        self.table_nodes: dict[str, TableNode] = {}
        self.cross_schema_relationships: list[dict[str, Any]] = []
        self.intra_schema_relationships: list[dict[str, Any]] = []

    async def analyze_schema_relationships(self, schemas: list[str]) -> str:
        """Analyze relationships between schemas and generate mapping data."""
        try:
            # Reset state
            self.schema_nodes = {}
            self.table_nodes = {}
            self.cross_schema_relationships = []
            self.intra_schema_relationships = []

            # Initialize schema nodes
            for schema in schemas:
                self.schema_nodes[schema] = SchemaNode(name=schema)

            # Analyze each schema
            for schema in schemas:
                await self._analyze_schema(schema)

            # Build relationship mappings
            await self._build_relationship_mappings()

            # Generate analysis results
            result = await self._generate_analysis_results()
            return self._format_as_text(result)

        except Exception as e:
            logger.error(f"Error analyzing schema relationships: {e}")
            return f"Error analyzing schema relationships: {e}"

    async def _analyze_schema(self, schema: str) -> None:
        """Analyze a single schema and populate node data."""
        try:
            # Get schema statistics
            schema_stats = await self._get_schema_statistics(schema)
            schema_node = self.schema_nodes[schema]
            schema_node.table_count = schema_stats["table_count"]
            schema_node.total_size_bytes = schema_stats["total_size_bytes"]
            schema_node.total_rows = schema_stats["total_rows"]

            # Get tables in schema
            tables = await self._get_tables_in_schema(schema)

            # Analyze each table
            for table in tables:
                await self._analyze_table(schema, table)

        except Exception as e:
            logger.error(f"Error analyzing schema {schema}: {e}")
            raise

    async def _analyze_table(self, schema: str, table: str) -> None:
        """Analyze a single table and its relationships."""
        try:
            qualified_name = f"{schema}.{table}"

            # Get table statistics
            table_stats = await self._get_table_statistics(schema, table)

            # Create table node
            table_node = TableNode(
                schema=schema,
                name=table,
                qualified_name=qualified_name,
                size_bytes=table_stats.get("size_bytes", 0),
                row_count=table_stats.get("row_count", 0),
            )

            # Get foreign key relationships
            fk_relationships = await self._get_foreign_key_relationships(schema, table)

            # Process outgoing foreign keys
            for fk in fk_relationships:
                target_qualified = f"{fk['to_schema']}.{fk['to_table']}"
                table_node.outgoing_fks.append(target_qualified)

                # Update schema-level relationships
                if fk["to_schema"] != schema:
                    self.schema_nodes[schema].outgoing_references.add(fk["to_schema"])
                    self.schema_nodes[fk["to_schema"]].incoming_references.add(schema)
                else:
                    self.schema_nodes[schema].self_references += 1

            self.table_nodes[qualified_name] = table_node

        except Exception as e:
            logger.error(f"Error analyzing table {schema}.{table}: {e}")
            raise

    async def _build_relationship_mappings(self) -> None:
        """Build comprehensive relationship mappings."""
        try:
            # Build incoming FK references for tables
            for table_name, table_node in self.table_nodes.items():
                for target_table in table_node.outgoing_fks:
                    if target_table in self.table_nodes:
                        self.table_nodes[target_table].incoming_fks.append(table_name)

            # Classify relationships
            for table_name, table_node in self.table_nodes.items():
                for target_table in table_node.outgoing_fks:
                    if target_table in self.table_nodes:
                        target_node = self.table_nodes[target_table]

                        relationship = {
                            "from_schema": table_node.schema,
                            "from_table": table_node.name,
                            "to_schema": target_node.schema,
                            "to_table": target_node.name,
                            "from_qualified": table_name,
                            "to_qualified": target_table,
                            "relationship_type": "cross_schema" if table_node.schema != target_node.schema else "intra_schema",
                        }

                        if table_node.schema != target_node.schema:
                            self.cross_schema_relationships.append(relationship)
                        else:
                            self.intra_schema_relationships.append(relationship)

        except Exception as e:
            logger.error(f"Error building relationship mappings: {e}")
            raise

    async def _generate_analysis_results(self) -> dict[str, Any]:
        """Generate comprehensive analysis results."""
        try:
            # Schema analysis
            schema_analysis = self._analyze_schema_dependencies()

            # Table analysis
            table_analysis = self._analyze_table_dependencies()

            # Relationship patterns
            relationship_patterns = self._analyze_relationship_patterns()

            # Visual representation data
            visual_data = self._generate_visual_representation()

            # Recommendations
            recommendations = self._generate_recommendations()

            return {
                "schema_analysis": schema_analysis,
                "table_analysis": table_analysis,
                "relationship_patterns": relationship_patterns,
                "visual_representation": visual_data,
                "recommendations": recommendations,
                "summary": {
                    "total_schemas": len(self.schema_nodes),
                    "total_tables": len(self.table_nodes),
                    "cross_schema_relationships": len(self.cross_schema_relationships),
                    "intra_schema_relationships": len(self.intra_schema_relationships),
                },
            }

        except Exception as e:
            logger.error(f"Error generating analysis results: {e}")
            raise

    def _analyze_schema_dependencies(self) -> dict[str, Any]:
        """Analyze schema-level dependencies."""
        schema_metrics = []

        for schema_name, schema_node in self.schema_nodes.items():
            metrics = {
                "schema": schema_name,
                "table_count": schema_node.table_count,
                "total_size_bytes": schema_node.total_size_bytes,
                "total_rows": schema_node.total_rows,
                "outgoing_dependencies": list(schema_node.outgoing_references),
                "incoming_dependencies": list(schema_node.incoming_references),
                "self_references": schema_node.self_references,
                "dependency_score": schema_node.dependency_score,
                "isolation_score": schema_node.isolation_score,
                "is_isolated": schema_node.isolation_score == 0,
            }
            schema_metrics.append(metrics)

        # Sort by dependency score
        schema_metrics.sort(key=lambda x: x["dependency_score"], reverse=True)

        return {
            "schema_metrics": schema_metrics,
            "most_dependent": schema_metrics[0] if schema_metrics else None,
            "most_isolated": min(schema_metrics, key=lambda x: x["isolation_score"]) if schema_metrics else None,
            "dependency_chains": self._find_dependency_chains(),
        }

    def _analyze_table_dependencies(self) -> dict[str, Any]:
        """Analyze table-level dependencies."""
        table_metrics = []
        hub_tables = []
        isolated_tables = []

        for table_name, table_node in self.table_nodes.items():
            metrics = {
                "qualified_name": table_name,
                "schema": table_node.schema,
                "table": table_node.name,
                "size_bytes": table_node.size_bytes,
                "row_count": table_node.row_count,
                "outgoing_fks": len(table_node.outgoing_fks),
                "incoming_fks": len(table_node.incoming_fks),
                "connection_count": table_node.connection_count,
                "is_hub": table_node.is_hub,
                "is_isolated": table_node.is_isolated,
            }
            table_metrics.append(metrics)

            if table_node.is_hub:
                hub_tables.append(metrics)

            if table_node.is_isolated:
                isolated_tables.append(metrics)

        # Sort by connection count
        table_metrics.sort(key=lambda x: x["connection_count"], reverse=True)

        return {
            "table_metrics": table_metrics,
            "hub_tables": sorted(hub_tables, key=lambda x: x["incoming_fks"], reverse=True),
            "isolated_tables": sorted(isolated_tables, key=lambda x: x["size_bytes"], reverse=True),
            "most_connected": table_metrics[0] if table_metrics else None,
        }

    def _analyze_relationship_patterns(self) -> dict[str, Any]:
        """Analyze relationship patterns and identify common structures."""
        patterns = {
            "cross_schema_count": len(self.cross_schema_relationships),
            "intra_schema_count": len(self.intra_schema_relationships),
            "total_relationships": len(self.cross_schema_relationships) + len(self.intra_schema_relationships),
        }

        # Analyze cross-schema patterns
        cross_schema_patterns = defaultdict(int)
        for rel in self.cross_schema_relationships:
            pattern = f"{rel['from_schema']} -> {rel['to_schema']}"
            cross_schema_patterns[pattern] += 1

        patterns["cross_schema_patterns"] = dict(cross_schema_patterns)
        patterns["most_common_cross_schema"] = max(cross_schema_patterns.items(), key=lambda x: x[1]) if cross_schema_patterns else None

        # Analyze schema coupling
        schema_coupling = {}
        for schema_name, schema_node in self.schema_nodes.items():
            total_external_refs = len(schema_node.outgoing_references) + len(schema_node.incoming_references)
            coupling_ratio = total_external_refs / max(schema_node.table_count, 1)
            schema_coupling[schema_name] = {
                "external_references": total_external_refs,
                "coupling_ratio": coupling_ratio,
                "coupling_level": self._categorize_coupling(coupling_ratio),
            }

        patterns["schema_coupling"] = schema_coupling

        return patterns

    def _generate_visual_representation(self) -> dict[str, Any]:
        """Generate data for visual representation of schema relationships."""
        # Node data for visualization
        nodes = []

        # Schema nodes
        for schema_name, schema_node in self.schema_nodes.items():
            node = {
                "id": schema_name,
                "type": "schema",
                "label": schema_name,
                "size": schema_node.total_size_bytes,
                "table_count": schema_node.table_count,
                "dependency_score": schema_node.dependency_score,
                "isolation_score": schema_node.isolation_score,
                "color": self._get_node_color(schema_node),
            }
            nodes.append(node)

        # Edge data for visualization
        edges = []
        edge_id = 0

        # Cross-schema relationships
        for rel in self.cross_schema_relationships:
            edge = {
                "id": f"edge_{edge_id}",
                "source": rel["from_schema"],
                "target": rel["to_schema"],
                "type": "cross_schema",
                "label": f"{rel['from_table']} -> {rel['to_table']}",
                "weight": 1,
            }
            edges.append(edge)
            edge_id += 1

        # Generate layout suggestions
        layout_data = self._generate_layout_suggestions()

        return {
            "nodes": nodes,
            "edges": edges,
            "layout": layout_data,
            "metrics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "density": len(edges) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0,
            },
        }

    def _generate_recommendations(self) -> list[dict[str, Any]]:
        """Generate recommendations based on schema analysis."""
        recommendations = []

        # High coupling warnings
        for schema_name, schema_node in self.schema_nodes.items():
            if len(schema_node.outgoing_references) > 3:
                recommendations.append(
                    {
                        "type": "warning",
                        "category": "high_coupling",
                        "schema": schema_name,
                        "message": f"Schema '{schema_name}' has high coupling with {len(schema_node.outgoing_references)} external dependencies",
                        "impact": "high",
                        "suggestion": "Consider consolidating related tables or reducing cross-schema dependencies",
                    }
                )

        # Isolated schema notifications
        for schema_name, schema_node in self.schema_nodes.items():
            if schema_node.isolation_score == 0 and schema_node.table_count > 5:
                recommendations.append(
                    {
                        "type": "info",
                        "category": "isolation",
                        "schema": schema_name,
                        "message": f"Schema '{schema_name}' is completely isolated with {schema_node.table_count} tables",
                        "impact": "low",
                        "suggestion": "Verify if this isolation is intentional or if relationships are missing",
                    }
                )

        # Hub table recommendations
        for table_name, table_node in self.table_nodes.items():
            if table_node.is_hub and len(table_node.incoming_fks) > 5:
                recommendations.append(
                    {
                        "type": "optimization",
                        "category": "hub_table",
                        "table": table_name,
                        "message": f"Table '{table_name}' is a hub with {len(table_node.incoming_fks)} incoming references",
                        "impact": "medium",
                        "suggestion": "Consider indexing strategies and monitoring performance for this central table",
                    }
                )

        return recommendations

    def _find_dependency_chains(self) -> list[list[str]]:
        """Find chains of schema dependencies."""
        chains = []
        visited = set()

        def dfs_chain(schema: str, path: list[str]):
            if schema in visited or schema in path:
                return

            path.append(schema)
            schema_node = self.schema_nodes.get(schema)

            if schema_node:
                if schema_node.outgoing_references:
                    for target_schema in schema_node.outgoing_references:
                        dfs_chain(target_schema, path.copy())
                else:
                    if len(path) > 1:
                        chains.append(path.copy())

            visited.add(schema)

        for schema in self.schema_nodes:
            if schema not in visited:
                dfs_chain(schema, [])

        return chains

    def _categorize_coupling(self, ratio: float) -> str:
        """Categorize coupling level based on ratio."""
        if ratio == 0:
            return "isolated"
        elif ratio <= 0.3:
            return "low"
        elif ratio <= 0.7:
            return "medium"
        else:
            return "high"

    def _get_node_color(self, schema_node: SchemaNode) -> str:
        """Get color for schema node based on characteristics."""
        if schema_node.isolation_score == 0:
            return "#gray"
        elif schema_node.dependency_score > 10:
            return "#red"
        elif schema_node.dependency_score > 5:
            return "#orange"
        else:
            return "#green"

    def _generate_layout_suggestions(self) -> dict[str, Any]:
        """Generate layout suggestions for visualization."""
        return {
            "recommended_layout": "force_directed",
            "clustering": True,
            "node_spacing": "medium",
            "edge_bundling": len(self.cross_schema_relationships) > 20,
        }

    # Helper methods for database queries

    async def _get_schema_statistics(self, schema: str) -> dict[str, Any]:
        """Get basic statistics for a schema."""
        query = """
            SELECT
                COUNT(*) as table_count,
                COALESCE(SUM(pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(relname))), 0) as total_size_bytes,
                COALESCE(SUM(n_live_tup), 0) as total_rows
            FROM pg_stat_user_tables
            WHERE schemaname = %s
        """

        try:
            rows = await self.sql_driver.execute_query(query, (schema,))
            if rows and rows[0]:
                return dict(rows[0].cells)
            return {"table_count": 0, "total_size_bytes": 0, "total_rows": 0}
        except Exception as e:
            logger.warning(f"Could not get schema statistics for {schema}: {e}")
            return {"table_count": 0, "total_size_bytes": 0, "total_rows": 0}

    async def _get_tables_in_schema(self, schema: str) -> list[str]:
        """Get list of tables in a schema."""
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """

        try:
            rows = await self.sql_driver.execute_query(query, (schema,))
            return [row.cells["table_name"] for row in rows] if rows else []
        except Exception as e:
            logger.warning(f"Could not get tables for schema {schema}: {e}")
            return []

    async def _get_table_statistics(self, schema: str, table: str) -> dict[str, Any]:
        """Get basic statistics for a table."""
        query = """
            SELECT
                pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(relname)) as size_bytes,
                COALESCE(n_live_tup, 0) as row_count
            FROM pg_stat_user_tables
            WHERE schemaname = %s AND relname = %s
        """

        try:
            rows = await self.sql_driver.execute_query(query, (schema, table))
            if rows and rows[0]:
                return dict(rows[0].cells)
            return {"size_bytes": 0, "row_count": 0}
        except Exception as e:
            logger.warning(f"Could not get table statistics for {schema}.{table}: {e}")
            return {"size_bytes": 0, "row_count": 0}

    async def _get_foreign_key_relationships(self, schema: str, table: str) -> list[dict[str, Any]]:
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

        try:
            rows = await self.sql_driver.execute_query(query, (schema, table))
            relationships = []

            for row in rows:
                relationship = {
                    "constraint_name": row.cells["constraint_name"],
                    "from_schema": row.cells["from_schema"],
                    "from_table": row.cells["from_table"],
                    "from_columns": row.cells["from_columns"].split(","),
                    "to_schema": row.cells["to_schema"],
                    "to_table": row.cells["to_table"],
                    "to_columns": row.cells["to_columns"].split(","),
                }
                relationships.append(relationship)

            return relationships
        except Exception as e:
            logger.warning(f"Could not get foreign key relationships for {schema}.{table}: {e}")
            return []

    def _format_as_text(self, result: dict[str, Any]) -> str:
        """Format schema relationship analysis as compact text (no emojis)."""
        if "error" in result:
            return f"Error: {result['error']}"

        out: list[str] = []

        # Summary (single line)
        summary = result.get("summary", {})
        out.append(
            "Summary: "
            f"schemas={summary.get('total_schemas', 0)} "
            f"tables={summary.get('total_tables', 0)} "
            f"cross={summary.get('cross_schema_relationships', 0)} "
            f"intra={summary.get('intra_schema_relationships', 0)}"
        )

        # Schema Analysis
        schema_analysis = result.get("schema_analysis", {})
        if schema_analysis:
            # Most dependent schema
            most_dependent = schema_analysis.get("most_dependent")
            if most_dependent:
                line = (
                    f"MostDependent: {most_dependent['schema']} "
                    f"dep_score={most_dependent['dependency_score']} "
                    f"out={len(most_dependent['outgoing_dependencies'])} "
                    f"in={len(most_dependent['incoming_dependencies'])}"
                )
                out.append(line)
                if most_dependent["outgoing_dependencies"]:
                    out.append("DependsOn: " + ", ".join(most_dependent["outgoing_dependencies"]))
                if most_dependent["incoming_dependencies"]:
                    out.append("DependedBy: " + ", ".join(most_dependent["incoming_dependencies"]))

            # Most isolated schema
            most_isolated = schema_analysis.get("most_isolated")
            if most_isolated and most_isolated["is_isolated"]:
                out.append(
                    f"MostIsolated: {most_isolated['schema']} "
                    f"tables={most_isolated['table_count']} "
                    f"size={self._format_bytes(most_isolated['total_size_bytes'])}"
                )

            # Schema metrics
            schema_metrics = schema_analysis.get("schema_metrics", [])
            if schema_metrics:
                for i, schema in enumerate(schema_metrics[:5], 1):
                    level = self._get_coupling_display(schema)
                    line = (
                        f"Schema{i}: {schema['schema']} level={level} "
                        f"tables={schema['table_count']} size={self._format_bytes(schema['total_size_bytes'])}"
                    )
                    out.append(line)
                    if schema["outgoing_dependencies"]:
                        out.append("  -> " + ", ".join(schema["outgoing_dependencies"]))
                    if schema["incoming_dependencies"]:
                        out.append("  <- " + ", ".join(schema["incoming_dependencies"]))

            # Dependency chains
            dependency_chains = schema_analysis.get("dependency_chains", [])
            if dependency_chains:
                chains = [" -> ".join(chain) for chain in dependency_chains[:5]]
                out.append("Chains: " + " | ".join(chains))

        # Table Analysis
        table_analysis = result.get("table_analysis", {})
        if table_analysis:
            # Most connected table
            most_connected = table_analysis.get("most_connected")
            if most_connected:
                out.append(
                    "MostConnected: "
                    f"{most_connected['qualified_name']} conn={most_connected['connection_count']} "
                    f"out={most_connected['outgoing_fks']} in={most_connected['incoming_fks']} "
                    f"size={self._format_bytes(most_connected['size_bytes'])}"
                )

            # Hub tables
            hub_tables = table_analysis.get("hub_tables", [])
            if hub_tables:
                hubs = [
                    f"{t['qualified_name']} in_fks={t['incoming_fks']} size={self._format_bytes(t['size_bytes'])} rows={t['row_count']}"
                    for t in hub_tables[:5]
                ]
                out.append("Hubs: " + "; ".join(hubs))

            # Isolated tables
            isolated_tables = table_analysis.get("isolated_tables", [])
            if isolated_tables:
                isolated_count = len(isolated_tables)
                out.append(f"Isolated: total={isolated_count}")
                if isolated_count > 0:
                    largest = [f"{t['qualified_name']} {self._format_bytes(t['size_bytes'])}" for t in isolated_tables[:5]]
                    out.append("IsolatedLargest: " + "; ".join(largest))

            output.append("")

        # Relationship Patterns
        relationship_patterns = result.get("relationship_patterns", {})
        if relationship_patterns:
            out.append(
                "Patterns: "
                f"cross={relationship_patterns.get('cross_schema_count', 0)} "
                f"intra={relationship_patterns.get('intra_schema_count', 0)} "
                f"total={relationship_patterns.get('total_relationships', 0)}"
            )

            # Most common cross-schema pattern
            most_common = relationship_patterns.get("most_common_cross_schema")
            if most_common:
                out.append(f"MostCommonCross: {most_common[0]} ({most_common[1]})")

            # Schema coupling analysis
            schema_coupling = relationship_patterns.get("schema_coupling", {})
            if schema_coupling:
                sorted_coupling = sorted(schema_coupling.items(), key=lambda x: x[1]["coupling_ratio"], reverse=True)
                for schema, coupling_data in sorted_coupling[:5]:
                    out.append(
                        f"Coupling: {schema} level={coupling_data['coupling_level']} "
                        f"ratio={coupling_data['coupling_ratio']:.2f} ext_refs={coupling_data['external_references']}"
                    )

            output.append("")

        # Recommendations
        recommendations = result.get("recommendations", [])
        if recommendations:
            # Group recommendations by type
            warnings = [r for r in recommendations if r["type"] == "warning"]
            optimizations = [r for r in recommendations if r["type"] == "optimization"]
            info = [r for r in recommendations if r["type"] == "info"]

            if warnings:
                out.append("Warnings: " + "; ".join([f"{r['message']} (suggest: {r['suggestion']})" for r in warnings]))

            if optimizations:
                out.append("Optimizations: " + "; ".join([f"{r['message']} (suggest: {r['suggestion']})" for r in optimizations]))

            if info:
                out.append("Info: " + "; ".join([f"{r['message']} (suggest: {r['suggestion']})" for r in info]))

        # Visual representation info
        visual_data = result.get("visual_representation", {})
        if visual_data:
            metrics = visual_data.get("metrics", {})
            if metrics:
                line = f"Viz: nodes={metrics.get('total_nodes', 0)} edges={metrics.get('total_edges', 0)} density={metrics.get('density', 0):.3f}"
                out.append(line)
                layout = visual_data.get("layout", {})
                if layout:
                    out.append(
                        "Layout: "
                        f"{layout.get('recommended_layout', 'N/A')} "
                        f"cluster={layout.get('clustering', False)} "
                        f"bundle={layout.get('edge_bundling', False)}"
                    )

        return "\n".join(out)

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

    def _get_coupling_display(self, schema: dict[str, Any]) -> str:
        """Get compact coupling level label."""
        score = schema.get("dependency_score", 0)
        isolation = schema.get("isolation_score", 0)
        if isolation == 0:
            return "isolated"
        if score > 10:
            return "high"
        if score > 5:
            return "medium"
        return "low"
