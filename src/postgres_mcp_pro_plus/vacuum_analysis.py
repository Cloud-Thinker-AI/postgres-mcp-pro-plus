"""Vacuum analysis tool for comprehensive database maintenance recommendations.

Extended from the original postgres-mcp project:
https://github.com/crystaldba/postgres-mcp
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VacuumAnalysisTool:
    """Tool for comprehensive vacuum analysis and maintenance recommendations."""

    def __init__(self, sql_driver):
        self.sql_driver = sql_driver

    async def analyze_vacuum_requirements(self) -> str:
        """Perform comprehensive vacuum analysis and return structured results."""
        try:
            logger.info("Starting comprehensive vacuum analysis...")

            analysis_results = {
                "summary": {},
                "bloat_analysis": {},
                "autovacuum_analysis": {},
                "vacuum_performance": {},
                "maintenance_recommendations": [],
                "critical_issues": [],
                "configuration_recommendations": [],
            }

            # Get basic statistics
            await self._get_vacuum_summary(analysis_results)

            # Analyze table bloat
            await self._analyze_table_bloat(analysis_results)

            # Analyze autovacuum configuration
            await self._analyze_autovacuum_config(analysis_results)

            # Analyze vacuum performance
            await self._analyze_vacuum_performance(analysis_results)

            # Generate maintenance recommendations
            await self._generate_maintenance_recommendations(analysis_results)

            # Check for critical issues
            await self._identify_critical_issues(analysis_results)

            # Generate configuration recommendations
            await self._generate_configuration_recommendations(analysis_results)

            logger.info("Vacuum analysis completed successfully")
            return self._format_as_text(analysis_results)

        except Exception as e:
            logger.error(f"Error in vacuum analysis: {e}")
            error_result = {
                "error": f"Vacuum analysis failed: {e!s}",
                "summary": {},
                "bloat_analysis": {},
                "autovacuum_analysis": {},
                "vacuum_performance": {},
                "maintenance_recommendations": [],
                "critical_issues": [],
                "configuration_recommendations": [],
            }
            return self._format_as_text(error_result)

    async def _get_vacuum_summary(self, analysis_results: dict[str, Any]) -> None:
        """Get high-level vacuum summary statistics."""
        query = """
            SELECT
                COUNT(*) as total_tables,
                COUNT(CASE WHEN last_vacuum IS NOT NULL OR last_autovacuum IS NOT NULL THEN 1 END) as tables_with_vacuum_history,
                COUNT(CASE WHEN last_vacuum IS NULL AND last_autovacuum IS NULL THEN 1 END) as tables_never_vacuumed,
                COUNT(CASE WHEN n_dead_tup > 0 THEN 1 END) as tables_with_dead_tuples,
                SUM(n_dead_tup) as total_dead_tuples,
                SUM(n_live_tup) as total_live_tuples,
                AVG(CASE WHEN n_live_tup + n_dead_tup > 0
                    THEN n_dead_tup::float / (n_live_tup + n_dead_tup) * 100
                    ELSE 0 END) as avg_dead_tuple_percentage,
                COUNT(CASE WHEN EXTRACT(EPOCH FROM (NOW() - COALESCE(last_autovacuum, last_vacuum))) > 86400 THEN 1 END) as tables_not_vacuumed_24h
            FROM pg_stat_user_tables
        """

        rows = await self.sql_driver.execute_query(query)
        if rows and rows[0]:
            data = rows[0].cells
            analysis_results["summary"] = {
                "total_tables": data["total_tables"],
                "tables_with_vacuum_history": data["tables_with_vacuum_history"],
                "tables_never_vacuumed": data["tables_never_vacuumed"],
                "tables_with_dead_tuples": data["tables_with_dead_tuples"],
                "total_dead_tuples": data["total_dead_tuples"],
                "total_live_tuples": data["total_live_tuples"],
                "avg_dead_tuple_percentage": round(data["avg_dead_tuple_percentage"] or 0.0, 2),
                "tables_not_vacuumed_24h": data["tables_not_vacuumed_24h"],
            }

    async def _analyze_table_bloat(self, analysis_results: dict[str, Any]) -> None:
        """Analyze table bloat and identify problematic tables."""
        query = """
            WITH bloat_analysis AS (
                SELECT
                    schemaname,
                    relname,
                    n_live_tup,
                    n_dead_tup,
                    CASE
                        WHEN n_live_tup + n_dead_tup > 0
                        THEN (n_dead_tup::float / (n_live_tup + n_dead_tup)) * 100
                        ELSE 0
                    END as dead_percentage,
                    pg_total_relation_size(schemaname||'.'||relname) as total_size_bytes,
                    CASE
                        WHEN n_live_tup > 0
                        THEN pg_total_relation_size(schemaname||'.'||relname) / n_live_tup
                        ELSE 0
                    END as bytes_per_tuple,
                    last_vacuum,
                    last_autovacuum,
                    vacuum_count,
                    autovacuum_count
                FROM pg_stat_user_tables
                WHERE n_live_tup + n_dead_tup > 0
            )
            SELECT *,
                CASE
                    WHEN dead_percentage > 40 THEN 'CRITICAL'
                    WHEN dead_percentage > 20 THEN 'HIGH'
                    WHEN dead_percentage > 10 THEN 'MEDIUM'
                    WHEN dead_percentage > 5 THEN 'LOW'
                    ELSE 'HEALTHY'
                END as bloat_severity,
                CASE
                    WHEN dead_percentage > 40 AND total_size_bytes > 100*1024*1024 THEN 'VACUUM FULL required'
                    WHEN dead_percentage > 20 THEN 'VACUUM required'
                    WHEN dead_percentage > 10 THEN 'VACUUM recommended'
                    ELSE 'No immediate action needed'
                END as recommendation
            FROM bloat_analysis
            ORDER BY dead_percentage DESC, total_size_bytes DESC
            LIMIT 50
        """

        rows = await self.sql_driver.execute_query(query)
        bloat_tables = []
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "HEALTHY": 0}

        if rows:
            for row in rows:
                data = row.cells
                bloat_tables.append(
                    {
                        "qualified_name": f"{data['schemaname']}.{data['relname']}",
                        "dead_percentage": round(data["dead_percentage"] or 0.0, 2),
                        "dead_tuples": data["n_dead_tup"],
                        "live_tuples": data["n_live_tup"],
                        "total_size_mb": round(data["total_size_bytes"] / (1024 * 1024), 2),
                        "bytes_per_tuple": data["bytes_per_tuple"],
                        "last_vacuum": data["last_vacuum"],
                        "last_autovacuum": data["last_autovacuum"],
                        "vacuum_count": data["vacuum_count"],
                        "autovacuum_count": data["autovacuum_count"],
                        "bloat_severity": data["bloat_severity"],
                        "recommendation": data["recommendation"],
                    }
                )
                severity_counts[data["bloat_severity"]] += 1

        analysis_results["bloat_analysis"] = {
            "tables": bloat_tables,
            "severity_distribution": severity_counts,
            "high_priority_tables": [t for t in bloat_tables if t["bloat_severity"] in ["CRITICAL", "HIGH"]],
        }

    async def _analyze_autovacuum_config(self, analysis_results: dict[str, Any]) -> None:
        """Analyze autovacuum configuration and effectiveness."""
        query = """
            WITH autovacuum_settings AS (
                SELECT
                    schemaname,
                    relname,
                    n_dead_tup,
                    n_live_tup,
                    COALESCE(
                        (SELECT setting FROM pg_settings WHERE name = 'autovacuum_vacuum_threshold'),
                        '50'
                    )::int as global_vacuum_threshold,
                    COALESCE(
                        (SELECT setting FROM pg_settings WHERE name = 'autovacuum_vacuum_scale_factor'),
                        '0.2'
                    )::float as global_vacuum_scale_factor,
                    last_autovacuum,
                    autovacuum_count,
                    n_tup_ins + n_tup_upd + n_tup_del as total_modifications,
                    EXTRACT(EPOCH FROM (NOW() - COALESCE(last_autovacuum, '1970-01-01'::timestamp))) / 3600 as hours_since_last_autovacuum
                FROM pg_stat_user_tables
                WHERE n_live_tup + n_dead_tup > 0
            )
            SELECT *,
                global_vacuum_threshold + (global_vacuum_scale_factor * n_live_tup) as calculated_threshold,
                CASE
                    WHEN n_dead_tup > (global_vacuum_threshold + (global_vacuum_scale_factor * n_live_tup))
                    THEN 'OVERDUE'
                    WHEN n_dead_tup > (global_vacuum_threshold + (global_vacuum_scale_factor * n_live_tup)) * 0.8
                    THEN 'APPROACHING'
                    ELSE 'HEALTHY'
                END as autovacuum_status,
                CASE
                    WHEN autovacuum_count > 0 AND total_modifications > 0
                    THEN total_modifications / autovacuum_count
                    ELSE 0
                END as avg_modifications_per_autovacuum
            FROM autovacuum_settings
            ORDER BY n_dead_tup DESC, hours_since_last_autovacuum DESC
            LIMIT 30
        """

        rows = await self.sql_driver.execute_query(query)
        autovacuum_tables = []
        status_counts = {"OVERDUE": 0, "APPROACHING": 0, "HEALTHY": 0}

        if rows:
            for row in rows:
                data = row.cells
                autovacuum_tables.append(
                    {
                        "qualified_name": f"{data['schemaname']}.{data['relname']}",
                        "dead_tuples": data["n_dead_tup"],
                        "live_tuples": data["n_live_tup"],
                        "calculated_threshold": round(data["calculated_threshold"] or 0.0, 0),
                        "autovacuum_status": data["autovacuum_status"],
                        "hours_since_last_autovacuum": round(data["hours_since_last_autovacuum"] or 0.0, 1),
                        "autovacuum_count": data["autovacuum_count"],
                        "avg_modifications_per_autovacuum": round(data["avg_modifications_per_autovacuum"] or 0.0, 0),
                    }
                )
                status_counts[data["autovacuum_status"]] += 1

        analysis_results["autovacuum_analysis"] = {
            "tables": autovacuum_tables,
            "status_distribution": status_counts,
            "problematic_tables": [
                t for t in autovacuum_tables if t["autovacuum_status"] in ["OVERDUE", "APPROACHING"]
            ],
        }

    async def _analyze_vacuum_performance(self, analysis_results: dict[str, Any]) -> None:
        """Analyze vacuum performance metrics."""
        query = """
            SELECT
                schemaname,
                relname,
                vacuum_count,
                autovacuum_count,
                last_vacuum,
                last_autovacuum,
                n_tup_ins + n_tup_upd + n_tup_del as total_modifications,
                CASE
                    WHEN vacuum_count + autovacuum_count > 0
                    THEN (n_tup_ins + n_tup_upd + n_tup_del) / (vacuum_count + autovacuum_count)
                    ELSE 0
                END as avg_modifications_per_vacuum,
                EXTRACT(EPOCH FROM (NOW() - COALESCE(last_autovacuum, last_vacuum))) / 3600 as hours_since_last_vacuum,
                pg_total_relation_size(schemaname||'.'||relname) as table_size_bytes,
                CASE
                    WHEN vacuum_count + autovacuum_count > 0
                    THEN pg_total_relation_size(schemaname||'.'||relname) / (vacuum_count + autovacuum_count)
                    ELSE 0
                END as avg_size_per_vacuum
            FROM pg_stat_user_tables
            WHERE n_tup_ins + n_tup_upd + n_tup_del > 0
            ORDER BY hours_since_last_vacuum DESC, total_modifications DESC
            LIMIT 25
        """

        rows = await self.sql_driver.execute_query(query)
        performance_tables = []

        if rows:
            for row in rows:
                data = row.cells
                performance_tables.append(
                    {
                        "qualified_name": f"{data['schemaname']}.{data['relname']}",
                        "vacuum_count": data["vacuum_count"],
                        "autovacuum_count": data["autovacuum_count"],
                        "total_modifications": data["total_modifications"],
                        "avg_modifications_per_vacuum": round(data["avg_modifications_per_vacuum"] or 0.0, 0),
                        "hours_since_last_vacuum": round(data["hours_since_last_vacuum"] or 0.0, 1),
                        "table_size_mb": round(data["table_size_bytes"] / (1024 * 1024), 2),
                        "avg_size_per_vacuum_mb": round((data["avg_size_per_vacuum"] or 0) / (1024 * 1024), 2),
                    }
                )

        analysis_results["vacuum_performance"] = {
            "tables": performance_tables,
            "stale_tables": [t for t in performance_tables if t["hours_since_last_vacuum"] > 72],  # >3 days
            "high_modification_tables": [t for t in performance_tables if t["total_modifications"] > 1000000],
        }

    async def _generate_maintenance_recommendations(self, analysis_results: dict[str, Any]) -> None:
        """Generate specific maintenance recommendations."""
        recommendations = []

        # Recommendations based on bloat analysis
        bloat_data = analysis_results.get("bloat_analysis", {})
        high_priority_bloat = bloat_data.get("high_priority_tables", [])

        for table in high_priority_bloat[:5]:  # Top 5 priority tables
            if table["bloat_severity"] == "CRITICAL":
                recommendations.append(
                    {
                        "type": "VACUUM_FULL",
                        "priority": "CRITICAL",
                        "table": table["qualified_name"],
                        "description": f"Table has {table['dead_percentage']}% dead tuples requiring VACUUM FULL",
                        "command": f"VACUUM FULL {table['qualified_name']};",
                        "estimated_impact": "High I/O, exclusive lock required",
                    }
                )
            elif table["bloat_severity"] == "HIGH":
                recommendations.append(
                    {
                        "type": "VACUUM",
                        "priority": "HIGH",
                        "table": table["qualified_name"],
                        "description": f"Table has {table['dead_percentage']}% dead tuples requiring VACUUM",
                        "command": f"VACUUM {table['qualified_name']};",
                        "estimated_impact": "Moderate I/O, shared lock",
                    }
                )

        # Recommendations based on autovacuum analysis
        autovacuum_data = analysis_results.get("autovacuum_analysis", {})
        problematic_autovacuum = autovacuum_data.get("problematic_tables", [])

        for table in problematic_autovacuum[:3]:  # Top 3 autovacuum issues
            if table["autovacuum_status"] == "OVERDUE":
                recommendations.append(
                    {
                        "type": "IMMEDIATE_VACUUM",
                        "priority": "HIGH",
                        "table": table["qualified_name"],
                        "description": f"Table is overdue for autovacuum ({table['dead_tuples']} dead tuples)",
                        "command": f"VACUUM {table['qualified_name']};",
                        "estimated_impact": "Should reduce dead tuple count",
                    }
                )

        # Recommendations based on performance analysis
        performance_data = analysis_results.get("vacuum_performance", {})
        stale_tables = performance_data.get("stale_tables", [])

        for table in stale_tables[:3]:  # Top 3 stale tables
            if table["hours_since_last_vacuum"] > 168:  # >1 week
                recommendations.append(
                    {
                        "type": "ANALYZE",
                        "priority": "MEDIUM",
                        "table": table["qualified_name"],
                        "description": f"Table hasn't been vacuumed in {table['hours_since_last_vacuum']:.1f} hours",
                        "command": f"ANALYZE {table['qualified_name']};",
                        "estimated_impact": "Update table statistics",
                    }
                )

        analysis_results["maintenance_recommendations"] = recommendations

    async def _identify_critical_issues(self, analysis_results: dict[str, Any]) -> None:
        """Identify critical issues requiring immediate attention."""
        critical_issues = []

        # Check transaction ID wraparound
        wraparound_query = """
            SELECT
                s.schemaname,
                s.relname,
                age(c.relfrozenxid) as xid_age,
                2000000000 - age(c.relfrozenxid) as xids_until_wraparound
            FROM pg_class c
            JOIN pg_namespace n ON c.relnamespace = n.oid
            JOIN pg_stat_user_tables s ON c.relname = s.relname AND n.nspname = s.schemaname
            WHERE c.relkind = 'r'
            AND age(c.relfrozenxid) > 1500000000
            ORDER BY age(c.relfrozenxid) DESC
            LIMIT 10
        """

        rows = await self.sql_driver.execute_query(wraparound_query)
        if rows:
            for row in rows:
                data = row.cells
                critical_issues.append(
                    {
                        "type": "TRANSACTION_ID_WRAPAROUND",
                        "severity": "CRITICAL",
                        "table": f"{data['schemaname']}.{data['relname']}",
                        "description": f"Table is approaching transaction ID wraparound (age: {data['xid_age']:,})",
                        "action_required": "Immediate VACUUM required",
                        "time_sensitive": True,
                    }
                )

        # Check for tables with extreme bloat
        bloat_data = analysis_results.get("bloat_analysis", {})
        for table in bloat_data.get("tables", []):
            if table["bloat_severity"] == "CRITICAL" and table["total_size_mb"] > 1000:  # >1GB
                critical_issues.append(
                    {
                        "type": "EXTREME_BLOAT",
                        "severity": "CRITICAL",
                        "table": table["qualified_name"],
                        "description": f"Large table ({table['total_size_mb']} MB) with {table['dead_percentage']}% dead tuples",
                        "action_required": "VACUUM FULL during maintenance window",
                        "time_sensitive": False,
                    }
                )

        analysis_results["critical_issues"] = critical_issues

    async def _generate_configuration_recommendations(self, analysis_results: dict[str, Any]) -> None:
        """Generate autovacuum configuration recommendations."""
        config_recommendations = []

        # Check current autovacuum settings
        settings_query = """
            SELECT
                name,
                setting,
                unit,
                short_desc
            FROM pg_settings
            WHERE name IN (
                'autovacuum',
                'autovacuum_max_workers',
                'autovacuum_naptime',
                'autovacuum_vacuum_threshold',
                'autovacuum_vacuum_scale_factor',
                'autovacuum_analyze_threshold',
                'autovacuum_analyze_scale_factor',
                'autovacuum_vacuum_cost_delay',
                'autovacuum_vacuum_cost_limit'
            )
            ORDER BY name
        """

        rows = await self.sql_driver.execute_query(settings_query)
        current_settings = {}
        if rows:
            for row in rows:
                data = row.cells
                current_settings[data["name"]] = {
                    "value": data["setting"],
                    "unit": data["unit"],
                    "description": data["short_desc"],
                }

        # Analyze if autovacuum is effective
        autovacuum_data = analysis_results.get("autovacuum_analysis", {})
        status_dist = autovacuum_data.get("status_distribution", {})

        if status_dist.get("OVERDUE", 0) > 5:
            config_recommendations.append(
                {
                    "parameter": "autovacuum_vacuum_scale_factor",
                    "current_value": current_settings.get("autovacuum_vacuum_scale_factor", {}).get("value", "unknown"),
                    "recommended_value": "0.1",
                    "reason": f"{status_dist['OVERDUE']} tables are overdue for autovacuum",
                    "impact": "More frequent autovacuum runs",
                }
            )

        if status_dist.get("OVERDUE", 0) > 10:
            config_recommendations.append(
                {
                    "parameter": "autovacuum_max_workers",
                    "current_value": current_settings.get("autovacuum_max_workers", {}).get("value", "unknown"),
                    "recommended_value": "6",
                    "reason": "High number of tables requiring vacuum",
                    "impact": "More parallel vacuum operations",
                }
            )

        # Check for large tables that might need custom settings
        bloat_data = analysis_results.get("bloat_analysis", {})
        large_bloated_tables = [
            t
            for t in bloat_data.get("tables", [])
            if t["total_size_mb"] > 10000 and t["bloat_severity"] in ["HIGH", "CRITICAL"]
        ]

        if large_bloated_tables:
            config_recommendations.append(
                {
                    "parameter": "table_specific_settings",
                    "current_value": "default",
                    "recommended_value": "custom per table",
                    "reason": f"{len(large_bloated_tables)} large tables with high bloat",
                    "impact": "Tailored autovacuum behavior for large tables",
                    "example_tables": [t["qualified_name"] for t in large_bloated_tables[:3]],
                }
            )

        analysis_results["configuration_recommendations"] = config_recommendations

    def _format_as_text(self, result: dict[str, Any]) -> str:
        """Format vacuum analysis result as human-readable text."""
        if "error" in result:
            return f"❌ Error: {result['error']}"

        output = []

        # Header
        output.append("🧹 VACUUM ANALYSIS REPORT")
        output.append("=" * 50)

        # Summary
        summary = result.get("summary", {})
        if summary:
            output.append("📊 SUMMARY")
            output.append("-" * 30)
            output.append(f"Total Tables: {summary.get('total_tables', 0)}")
            output.append(f"Tables with Vacuum History: {summary.get('tables_with_vacuum_history', 0)}")
            output.append(f"Tables Never Vacuumed: {summary.get('tables_never_vacuumed', 0)}")
            output.append(f"Tables with Dead Tuples: {summary.get('tables_with_dead_tuples', 0)}")
            output.append(f"Total Dead Tuples: {summary.get('total_dead_tuples', 0):,}")
            output.append(f"Total Live Tuples: {summary.get('total_live_tuples', 0):,}")
            output.append(f"Average Dead Tuple %: {summary.get('avg_dead_tuple_percentage', 0):.2f}%")
            output.append(f"Tables Not Vacuumed (24h): {summary.get('tables_not_vacuumed_24h', 0)}")
            output.append("")

        # Critical Issues
        critical_issues = result.get("critical_issues", [])
        if critical_issues:
            output.append("🚨 CRITICAL ISSUES")
            output.append("-" * 30)
            for i, issue in enumerate(critical_issues, 1):
                output.append(f"{i}. {issue['type']}")
                output.append(f"   Severity: {issue['severity']}")
                output.append(f"   Table: {issue['table']}")
                output.append(f"   Description: {issue['description']}")
                output.append(f"   Action Required: {issue['action_required']}")
                if issue.get("time_sensitive"):
                    output.append(f"   ⏰ TIME SENSITIVE")
                output.append("")

        # Bloat Analysis
        bloat_analysis = result.get("bloat_analysis", {})
        if bloat_analysis:
            output.append("💀 BLOAT ANALYSIS")
            output.append("-" * 30)

            severity_dist = bloat_analysis.get("severity_distribution", {})
            output.append(f"Severity Distribution:")
            for severity, count in severity_dist.items():
                if count > 0:
                    severity_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "HEALTHY": "✅"}.get(
                        severity, "⚪"
                    )
                    output.append(f"  {severity_emoji} {severity}: {count} tables")

            high_priority = bloat_analysis.get("high_priority_tables", [])
            if high_priority:
                output.append(f"\n🎯 High Priority Tables ({len(high_priority)}):")
                for table in high_priority[:10]:  # Show top 10
                    output.append(f"  • {table['qualified_name']}")
                    output.append(
                        f"    Dead Tuples: {table['dead_percentage']:.1f}% ({table['dead_tuples']:,} dead, {table['live_tuples']:,} live)"
                    )
                    output.append(f"    Size: {table['total_size_mb']:.1f} MB")
                    output.append(f"    Severity: {table['bloat_severity']}")
                    output.append(f"    Recommendation: {table['recommendation']}")

                    if table["last_vacuum"]:
                        output.append(f"    Last Manual Vacuum: {table['last_vacuum']}")
                    if table["last_autovacuum"]:
                        output.append(f"    Last Autovacuum: {table['last_autovacuum']}")
                    output.append("")

        # Autovacuum Analysis
        autovacuum_analysis = result.get("autovacuum_analysis", {})
        if autovacuum_analysis:
            output.append("🤖 AUTOVACUUM ANALYSIS")
            output.append("-" * 30)

            status_dist = autovacuum_analysis.get("status_distribution", {})
            output.append(f"Status Distribution:")
            for status, count in status_dist.items():
                if count > 0:
                    status_emoji = {"OVERDUE": "🔴", "APPROACHING": "🟡", "HEALTHY": "✅"}.get(status, "⚪")
                    output.append(f"  {status_emoji} {status}: {count} tables")

            problematic = autovacuum_analysis.get("problematic_tables", [])
            if problematic:
                output.append(f"\n⚠️ Problematic Tables ({len(problematic)}):")
                for table in problematic[:10]:  # Show top 10
                    output.append(f"  • {table['qualified_name']}")
                    output.append(f"    Status: {table['autovacuum_status']}")
                    output.append(
                        f"    Dead Tuples: {table['dead_tuples']:,} (threshold: {table['calculated_threshold']:,.0f})"
                    )
                    output.append(f"    Hours Since Last Autovacuum: {table['hours_since_last_autovacuum']:.1f}")
                    output.append(f"    Autovacuum Count: {table['autovacuum_count']}")
                    output.append("")

        # Vacuum Performance
        vacuum_performance = result.get("vacuum_performance", {})
        if vacuum_performance:
            output.append("⚡ VACUUM PERFORMANCE")
            output.append("-" * 30)

            stale_tables = vacuum_performance.get("stale_tables", [])
            if stale_tables:
                output.append(f"📅 Stale Tables ({len(stale_tables)}):")
                for table in stale_tables[:5]:  # Show top 5
                    output.append(f"  • {table['qualified_name']}")
                    output.append(f"    Hours Since Last Vacuum: {table['hours_since_last_vacuum']:.1f}")
                    output.append(f"    Size: {table['table_size_mb']:.1f} MB")
                    output.append(f"    Total Modifications: {table['total_modifications']:,}")
                    output.append("")

            high_mod_tables = vacuum_performance.get("high_modification_tables", [])
            if high_mod_tables:
                output.append(f"🔥 High Modification Tables ({len(high_mod_tables)}):")
                for table in high_mod_tables[:5]:  # Show top 5
                    output.append(f"  • {table['qualified_name']}")
                    output.append(f"    Total Modifications: {table['total_modifications']:,}")
                    output.append(f"    Vacuum Count: {table['vacuum_count']}")
                    output.append(f"    Autovacuum Count: {table['autovacuum_count']}")
                    output.append("")

        # Maintenance Recommendations
        maintenance_recs = result.get("maintenance_recommendations", [])
        if maintenance_recs:
            output.append("🔧 MAINTENANCE RECOMMENDATIONS")
            output.append("-" * 40)

            # Group by priority
            critical_recs = [r for r in maintenance_recs if r["priority"] == "CRITICAL"]
            high_recs = [r for r in maintenance_recs if r["priority"] == "HIGH"]
            medium_recs = [r for r in maintenance_recs if r["priority"] == "MEDIUM"]

            if critical_recs:
                output.append("🚨 CRITICAL PRIORITY:")
                for rec in critical_recs:
                    output.append(f"  • {rec['type']}: {rec['table']}")
                    output.append(f"    Description: {rec['description']}")
                    output.append(f"    Command: {rec['command']}")
                    output.append(f"    Impact: {rec['estimated_impact']}")
                    output.append("")

            if high_recs:
                output.append("🔴 HIGH PRIORITY:")
                for rec in high_recs:
                    output.append(f"  • {rec['type']}: {rec['table']}")
                    output.append(f"    Description: {rec['description']}")
                    output.append(f"    Command: {rec['command']}")
                    output.append(f"    Impact: {rec['estimated_impact']}")
                    output.append("")

            if medium_recs:
                output.append("🟡 MEDIUM PRIORITY:")
                for rec in medium_recs:
                    output.append(f"  • {rec['type']}: {rec['table']}")
                    output.append(f"    Description: {rec['description']}")
                    output.append(f"    Command: {rec['command']}")
                    output.append(f"    Impact: {rec['estimated_impact']}")
                    output.append("")

        # Configuration Recommendations
        config_recs = result.get("configuration_recommendations", [])
        if config_recs:
            output.append("⚙️ CONFIGURATION RECOMMENDATIONS")
            output.append("-" * 40)

            for i, rec in enumerate(config_recs, 1):
                output.append(f"{i}. Parameter: {rec['parameter']}")
                output.append(f"   Current Value: {rec['current_value']}")
                output.append(f"   Recommended Value: {rec['recommended_value']}")
                output.append(f"   Reason: {rec['reason']}")
                output.append(f"   Impact: {rec['impact']}")

                if "example_tables" in rec:
                    output.append(f"   Example Tables: {', '.join(rec['example_tables'])}")
                output.append("")

        # Summary recommendations
        if not critical_issues and not maintenance_recs:
            output.append("✅ OVERALL STATUS")
            output.append("-" * 30)
            output.append("• No critical vacuum issues detected")
            output.append("• Autovacuum appears to be functioning normally")
            output.append("• Continue regular monitoring")
            output.append("")

            output.append("💡 GENERAL RECOMMENDATIONS")
            output.append("-" * 30)
            output.append("• Monitor dead tuple percentages regularly")
            output.append("• Review autovacuum settings periodically")
            output.append("• Consider manual vacuum during low-activity periods")
            output.append("• Keep PostgreSQL statistics up to date")

        return "\n".join(output)
