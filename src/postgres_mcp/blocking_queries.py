"""
Blocking queries analysis tool for PostgreSQL databases.
Provides comprehensive analysis of query locks and blocking relationships.
"""

import logging
from typing import Any, Dict, List
from datetime import datetime

from .sql import SqlDriver

logger = logging.getLogger(__name__)


class BlockingQueriesAnalyzer:
    """Analyzer for PostgreSQL blocking queries and lock contention."""

    def __init__(self, sql_driver: SqlDriver):
        self.sql_driver = sql_driver

    async def get_blocking_queries(self) -> Dict[str, Any]:
        """
        Get comprehensive blocking queries analysis using modern PostgreSQL features.

        Returns:
            Dict containing blocking queries data, summary, and recommendations
        """
        try:
            # Modern blocking queries query using pg_blocking_pids (PostgreSQL 9.6+)
            blocking_query = """
                WITH blocking_tree AS (
                    SELECT
                        activity.pid,
                        activity.usename,
                        activity.application_name,
                        activity.client_addr,
                        activity.state,
                        activity.query,
                        activity.query_start,
                        activity.state_change,
                        activity.wait_event,
                        activity.wait_event_type,
                        pg_blocking_pids(activity.pid) AS blocking_pids,
                        EXTRACT(EPOCH FROM (now() - activity.query_start)) AS duration_seconds,
                        EXTRACT(EPOCH FROM (now() - activity.state_change)) AS state_duration_seconds,
                        CASE WHEN activity.query_start IS NOT NULL
                            THEN EXTRACT(EPOCH FROM (now() - activity.query_start))
                            ELSE NULL END AS wait_duration_seconds
                    FROM pg_stat_activity activity
                    WHERE activity.pid <> pg_backend_pid()
                        AND activity.state IS NOT NULL
                ),
                lock_details AS (
                    SELECT
                        pid,
                        string_agg(DISTINCT locktype, ', ') AS lock_types,
                        string_agg(DISTINCT mode, ', ') AS lock_modes,
                        COUNT(*) AS lock_count,
                        string_agg(DISTINCT CASE
                            WHEN relation IS NOT NULL THEN
                                (SELECT schemaname||'.'||relname
                                 FROM pg_stat_user_tables
                                 WHERE relid = relation)
                            ELSE NULL END, ', ') AS affected_relations
                    FROM pg_locks
                    WHERE granted = false
                    GROUP BY pid
                )
                SELECT
                    bt.pid AS blocked_pid,
                    bt.usename AS blocked_user,
                    bt.application_name AS blocked_application,
                    bt.client_addr AS blocked_client_addr,
                    bt.state AS blocked_state,
                    bt.query AS blocked_query,
                    bt.query_start AS blocked_query_start,
                    bt.state_change AS blocked_state_change,
                    bt.wait_event AS blocked_wait_event,
                    bt.wait_event_type AS blocked_wait_event_type,
                    bt.duration_seconds AS blocked_duration_seconds,
                    bt.state_duration_seconds AS blocked_state_duration_seconds,
                    bt.wait_duration_seconds AS blocked_wait_duration_seconds,
                    bt.blocking_pids,
                    blocker.pid AS blocking_pid,
                    blocker.usename AS blocking_user,
                    blocker.application_name AS blocking_application,
                    blocker.client_addr AS blocking_client_addr,
                    blocker.state AS blocking_state,
                    blocker.query AS blocking_query,
                    blocker.query_start AS blocking_query_start,
                    blocker.duration_seconds AS blocking_duration_seconds,
                    ld.lock_types,
                    ld.lock_modes,
                    ld.lock_count,
                    ld.affected_relations
                FROM blocking_tree bt
                LEFT JOIN LATERAL unnest(bt.blocking_pids) AS blocking_pid_unnest(pid) ON true
                LEFT JOIN blocking_tree blocker ON blocker.pid = blocking_pid_unnest.pid
                LEFT JOIN lock_details ld ON ld.pid = bt.pid
                WHERE cardinality(bt.blocking_pids) > 0
                ORDER BY bt.duration_seconds DESC;
            """
            rows = await self.sql_driver.execute_query(blocking_query)

            if not rows or len(rows) == 0:
                return {
                    "status": "healthy",
                    "message": "No blocking queries found - all queries are running without locks.",
                    "blocking_queries": [],
                    "summary": {
                        "total_blocked": 0,
                        "total_blocking": 0,
                        "max_wait_time": 0,
                        "affected_relations": []
                    },
                    "recommendations": []
                }

            # Process blocking queries data with improved structure
            blocking_data = []
            blocking_pids = set()
            blocked_pids = set()
            relations = set()
            max_wait_time = 0

            for row in rows:
                duration = float(row.cells["blocked_duration_seconds"]) if row.cells["blocked_duration_seconds"] else 0
                max_wait_time = max(max_wait_time, duration)

                if row.cells["blocking_pid"]:
                    blocking_pids.add(row.cells["blocking_pid"])
                blocked_pids.add(row.cells["blocked_pid"])

                if row.cells["affected_relations"]:
                    relations.update(row.cells["affected_relations"].split(", "))

                blocking_data.append({
                    "blocked_process": {
                        "pid": row.cells["blocked_pid"],
                        "user": row.cells["blocked_user"],
                        "application": row.cells["blocked_application"],
                        "client_addr": row.cells["blocked_client_addr"],
                        "state": row.cells["blocked_state"],
                        "query_start": row.cells["blocked_query_start"],
                        "state_change": row.cells["blocked_state_change"],
                        "wait_event": row.cells["blocked_wait_event"],
                        "wait_event_type": row.cells["blocked_wait_event_type"],
                        "duration_seconds": duration,
                        "state_duration_seconds": float(row.cells["blocked_state_duration_seconds"]) if row.cells["blocked_state_duration_seconds"] else 0,
                        "wait_duration_seconds": float(row.cells["blocked_wait_duration_seconds"]) if row.cells["blocked_wait_duration_seconds"] else 0,
                        "query": row.cells["blocked_query"]
                    },
                    "blocking_process": {
                        "pid": row.cells["blocking_pid"],
                        "user": row.cells["blocking_user"],
                        "application": row.cells["blocking_application"],
                        "client_addr": row.cells["blocking_client_addr"],
                        "state": row.cells["blocking_state"],
                        "query_start": row.cells["blocking_query_start"],
                        "duration_seconds": float(row.cells["blocking_duration_seconds"]) if row.cells["blocking_duration_seconds"] else 0,
                        "query": row.cells["blocking_query"]
                    },
                    "lock_info": {
                        "types": row.cells["lock_types"],
                        "modes": row.cells["lock_modes"],
                        "count": row.cells["lock_count"],
                        "affected_relations": row.cells["affected_relations"]
                    },
                    "blocking_hierarchy": {
                        "all_blocking_pids": row.cells["blocking_pids"],
                        "immediate_blocker": row.cells["blocking_pid"]
                    }
                })

            # Generate summary and recommendations
            summary = {
                "total_blocked": len(blocked_pids),
                "total_blocking": len(blocking_pids),
                "max_wait_time_seconds": max_wait_time,
                "affected_relations": list(relations),
                "analysis_timestamp": datetime.now().isoformat()
            }

            recommendations = self._generate_recommendations(blocking_data, summary)

            return {
                "status": "blocking_detected",
                "blocking_queries": blocking_data,
                "summary": summary,
                "recommendations": recommendations
            }
        except Exception as e:
            logger.error(f"Error analyzing blocking queries: {e}")
            raise

    async def get_lock_summary(self) -> Dict[str, Any]:
        """Get a summary of all locks in the database."""
        try:
            lock_summary_query = """
                SELECT
                    locktype,
                    mode,
                    granted,
                    COUNT(*) as lock_count
                FROM pg_locks
                GROUP BY locktype, mode, granted
                ORDER BY lock_count DESC;
            """

            rows = await self.sql_driver.execute_query(lock_summary_query)

            lock_summary = []
            if rows:
                for row in rows:
                    lock_summary.append({
                        "lock_type": row.cells["locktype"],
                        "mode": row.cells["mode"],
                        "granted": row.cells["granted"],
                        "count": row.cells["lock_count"]
                    })

            return {
                "lock_summary": lock_summary,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting lock summary: {e}")
            raise

    async def get_deadlock_info(self) -> Dict[str, Any]:
        """Get recent deadlock information from PostgreSQL logs."""
        try:
            # Query for deadlock detection settings and stats
            deadlock_query = """
                SELECT
                    name,
                    setting,
                    unit,
                    category
                FROM pg_settings
                WHERE name IN (
                    'deadlock_timeout',
                    'log_lock_waits',
                    'lock_timeout'
                );
            """

            rows = await self.sql_driver.execute_query(deadlock_query)

            settings = {}
            if rows:
                for row in rows:
                    settings[row.cells["name"]] = {
                        "value": row.cells["setting"],
                        "unit": row.cells["unit"],
                        "category": row.cells["category"]
                    }

            return {
                "deadlock_settings": settings,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting deadlock info: {e}")
            raise

    def _generate_recommendations(self, blocking_data: List[Dict[str, Any]], summary: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on blocking query analysis."""
        recommendations = []

        if summary["max_wait_time_seconds"] > 300:  # 5 minutes
            recommendations.append(
                f"🚨 CRITICAL: Queries have been blocked for {summary['max_wait_time_seconds']:.1f} seconds. "
                "Consider terminating long-running blocking queries."
            )
        elif summary["max_wait_time_seconds"] > 60:  # 1 minute
            recommendations.append(
                f"⚠️ WARNING: Queries blocked for {summary['max_wait_time_seconds']:.1f} seconds. "
                "Monitor closely and consider intervention."
            )

        if summary["total_blocked"] > 10:
            recommendations.append(
                f"🚨 HIGH CONTENTION: {summary['total_blocked']} queries are blocked. "
                "This indicates high lock contention - review query patterns and indexing."
            )

        # Analyze lock types and patterns from the improved lock_info structure
        lock_types = {}
        for block in blocking_data:
            lock_info_types = block["lock_info"]["types"]
            if lock_info_types:
                for lock_type in lock_info_types.split(", "):
                    lock_types[lock_type] = lock_types.get(lock_type, 0) + 1

        if "transactionid" in lock_types and lock_types["transactionid"] > 3:
            recommendations.append(
                "💡 OPTIMIZATION: Multiple transaction ID locks detected. "
                "Consider shortening transaction duration and avoiding long-running transactions."
            )

        if "relation" in lock_types:
            recommendations.append(
                "💡 OPTIMIZATION: Table-level locks detected. "
                "Review queries for table scans and consider adding appropriate indexes."
            )

        # Check for same relations being blocked multiple times
        if len(summary["affected_relations"]) < summary["total_blocked"] / 2:
            recommendations.append(
                "🎯 HOTSPOT: Multiple queries are contending for the same tables. "
                "Focus optimization efforts on these hot tables: " +
                ", ".join(summary["affected_relations"])
            )

        # Add recommendations based on wait events
        wait_events = {}
        for block in blocking_data:
            wait_event = block["blocked_process"]["wait_event"]
            if wait_event:
                wait_events[wait_event] = wait_events.get(wait_event, 0) + 1

        if "Lock" in wait_events:
            recommendations.append(
                "🔒 LOCK ANALYSIS: High lock contention detected. "
                "Consider query optimization, index tuning, or connection pooling."
            )

        if not recommendations:
            recommendations.append(
                "✅ Current blocking situation appears manageable. Monitor for patterns and trends."
            )

        return recommendations
