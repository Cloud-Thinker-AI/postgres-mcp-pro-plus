"""
Blocking queries analysis tool for PostgreSQL databases.
Provides comprehensive analysis of query locks and blocking relationships.
"""

import logging
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

from .sql import SqlDriver

logger = logging.getLogger(__name__)


class BlockingQueriesAnalyzer:
    """Analyzer for PostgreSQL blocking queries and lock contention."""

    def __init__(self, sql_driver: SqlDriver):
        self.sql_driver = sql_driver

    async def get_blocking_queries(self) -> str:
        """
        Get comprehensive blocking queries analysis using modern PostgreSQL features.
        Enhanced with lock wait graph visualization, deadlock detection, session termination
        recommendations, lock timeout suggestions, and historical analysis.

        Returns:
            String containing blocking queries data, summary, and recommendations
        """
        try:
            # Get comprehensive blocking analysis
            blocking_data = await self._get_blocking_data()

            if not blocking_data:
                # Get deadlock information even when no current blocking
                deadlock_info = await self._get_deadlock_analysis()
                lock_contention_hotspots = await self._get_lock_contention_hotspots()

                result = {
                    "status": "healthy",
                    "message": "No blocking queries found - all queries are running without locks.",
                    "blocking_queries": [],
                    "summary": {"total_blocked": 0, "total_blocking": 0, "max_wait_time": 0, "affected_relations": []},
                    "deadlock_analysis": deadlock_info,
                    "lock_contention_hotspots": lock_contention_hotspots,
                    "recommendations": await self._generate_healthy_recommendations(),
                }
                return self._format_as_text(result)

            # Enhanced analysis for blocking queries
            lock_wait_graph = await self._generate_lock_wait_graph(blocking_data)
            deadlock_info = await self._get_deadlock_analysis()
            session_termination_recs = await self._generate_session_termination_recommendations(blocking_data)
            lock_timeout_suggestions = await self._generate_lock_timeout_suggestions(blocking_data)
            historical_analysis = await self._get_historical_blocking_analysis()
            lock_escalation_info = await self._detect_lock_escalation(blocking_data)
            query_pattern_analysis = await self._analyze_query_patterns(blocking_data)
            batch_operation_impact = await self._analyze_batch_operation_impact(blocking_data)
            lock_contention_hotspots = await self._get_lock_contention_hotspots()

            # Process blocking queries data with improved structure
            blocking_pids = set()
            blocked_pids = set()
            relations = set()
            max_wait_time = 0

            for block in blocking_data:
                duration = block["blocked_process"]["duration_seconds"]
                max_wait_time = max(max_wait_time, duration)

                if block["blocking_process"]["pid"]:
                    blocking_pids.add(block["blocking_process"]["pid"])
                blocked_pids.add(block["blocked_process"]["pid"])

                if block["lock_info"]["affected_relations"]:
                    relations.update(block["lock_info"]["affected_relations"].split(", "))

            # Generate enhanced summary
            summary = {
                "total_blocked": len(blocked_pids),
                "total_blocking": len(blocking_pids),
                "max_wait_time_seconds": max_wait_time,
                "affected_relations": list(relations),
                "analysis_timestamp": datetime.now().isoformat(),
                "lock_wait_threshold_alerts": self._check_lock_wait_thresholds(blocking_data),
            }

            recommendations = await self._generate_enhanced_recommendations(
                blocking_data,
                summary,
                session_termination_recs,
                lock_timeout_suggestions,
                historical_analysis,
                lock_escalation_info,
                query_pattern_analysis,
            )

            result = {
                "status": "blocking_detected",
                "blocking_queries": blocking_data,
                "summary": summary,
                "lock_wait_graph": lock_wait_graph,
                "deadlock_analysis": deadlock_info,
                "session_termination_recommendations": session_termination_recs,
                "lock_timeout_suggestions": lock_timeout_suggestions,
                "historical_analysis": historical_analysis,
                "lock_escalation_detection": lock_escalation_info,
                "query_pattern_analysis": query_pattern_analysis,
                "batch_operation_impact": batch_operation_impact,
                "lock_contention_hotspots": lock_contention_hotspots,
                "recommendations": recommendations,
            }
            return self._format_as_text(result)
        except Exception as e:
            logger.error(f"Error analyzing blocking queries: {e}")
            raise

    async def _get_blocking_data(self) -> List[Dict[str, Any]]:
        """Get comprehensive blocking queries data using modern PostgreSQL features."""
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
                        ELSE NULL END AS wait_duration_seconds,
                    activity.backend_start,
                    activity.xact_start
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
                        ELSE NULL END, ', ') AS affected_relations,
                    -- Enhanced lock information
                    string_agg(DISTINCT CASE
                        WHEN locktype = 'relation' AND mode LIKE '%ExclusiveLock' THEN 'TABLE_LOCK'
                        WHEN locktype = 'tuple' THEN 'ROW_LOCK'
                        WHEN locktype = 'transactionid' THEN 'TXN_LOCK'
                        ELSE locktype END, ', ') AS lock_categories
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
                bt.backend_start AS blocked_backend_start,
                bt.xact_start AS blocked_xact_start,
                bt.blocking_pids,
                blocker.pid AS blocking_pid,
                blocker.usename AS blocking_user,
                blocker.application_name AS blocking_application,
                blocker.client_addr AS blocking_client_addr,
                blocker.state AS blocking_state,
                blocker.query AS blocking_query,
                blocker.query_start AS blocking_query_start,
                blocker.duration_seconds AS blocking_duration_seconds,
                blocker.backend_start AS blocking_backend_start,
                blocker.xact_start AS blocking_xact_start,
                ld.lock_types,
                ld.lock_modes,
                ld.lock_count,
                ld.affected_relations,
                ld.lock_categories
            FROM blocking_tree bt
            LEFT JOIN LATERAL unnest(bt.blocking_pids) AS blocking_pid_unnest(pid) ON true
            LEFT JOIN blocking_tree blocker ON blocker.pid = blocking_pid_unnest.pid
            LEFT JOIN lock_details ld ON ld.pid = bt.pid
            WHERE cardinality(bt.blocking_pids) > 0
            ORDER BY bt.duration_seconds DESC;
        """

        rows = await self.sql_driver.execute_query(blocking_query)
        if not rows:
            return []

        blocking_data = []
        for row in rows:
            duration = float(row.cells["blocked_duration_seconds"]) if row.cells["blocked_duration_seconds"] else 0

            blocking_data.append(
                {
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
                        "state_duration_seconds": (
                            float(row.cells["blocked_state_duration_seconds"]) if row.cells["blocked_state_duration_seconds"] else 0
                        ),
                        "wait_duration_seconds": (
                            float(row.cells["blocked_wait_duration_seconds"]) if row.cells["blocked_wait_duration_seconds"] else 0
                        ),
                        "query": row.cells["blocked_query"],
                        "backend_start": row.cells["blocked_backend_start"],
                        "xact_start": row.cells["blocked_xact_start"],
                    },
                    "blocking_process": {
                        "pid": row.cells["blocking_pid"],
                        "user": row.cells["blocking_user"],
                        "application": row.cells["blocking_application"],
                        "client_addr": row.cells["blocking_client_addr"],
                        "state": row.cells["blocking_state"],
                        "query_start": row.cells["blocking_query_start"],
                        "duration_seconds": float(row.cells["blocking_duration_seconds"]) if row.cells["blocking_duration_seconds"] else 0,
                        "query": row.cells["blocking_query"],
                        "backend_start": row.cells["blocking_backend_start"],
                        "xact_start": row.cells["blocking_xact_start"],
                    },
                    "lock_info": {
                        "types": row.cells["lock_types"],
                        "modes": row.cells["lock_modes"],
                        "count": row.cells["lock_count"],
                        "affected_relations": row.cells["affected_relations"],
                        "categories": row.cells["lock_categories"],
                    },
                    "blocking_hierarchy": {
                        "all_blocking_pids": row.cells["blocking_pids"],
                        "immediate_blocker": row.cells["blocking_pid"],
                    },
                }
            )

        return blocking_data

    async def _generate_lock_wait_graph(self, blocking_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate visual representation of blocking hierarchies."""
        try:
            graph = {
                "nodes": [],
                "edges": [],
                "visualization_data": {
                    "blocking_chains": [],
                    "circular_dependencies": [],
                    "root_blockers": [],
                    "leaf_blocked": [],
                },
            }

            # Build nodes and edges
            all_pids = set()
            blocking_relationships = {}

            for block in blocking_data:
                blocked_pid = block["blocked_process"]["pid"]
                blocking_pid = block["blocking_process"]["pid"]

                all_pids.add(blocked_pid)
                if blocking_pid:
                    all_pids.add(blocking_pid)
                    blocking_relationships[blocked_pid] = blocking_pid

            # Create nodes
            for pid in all_pids:
                # Find process info
                process_info = None
                for block in blocking_data:
                    if block["blocked_process"]["pid"] == pid:
                        process_info = block["blocked_process"]
                        break
                    elif block["blocking_process"]["pid"] == pid:
                        process_info = block["blocking_process"]
                        break

                if process_info:
                    graph["nodes"].append(
                        {
                            "pid": pid,
                            "user": process_info.get("user", "unknown"),
                            "application": process_info.get("application", "unknown"),
                            "state": process_info.get("state", "unknown"),
                            "duration": process_info.get("duration_seconds", 0),
                            "is_blocker": pid in [b["blocking_process"]["pid"] for b in blocking_data if b["blocking_process"]["pid"]],
                            "is_blocked": pid in [b["blocked_process"]["pid"] for b in blocking_data],
                        }
                    )

            # Create edges
            for blocked_pid, blocking_pid in blocking_relationships.items():
                graph["edges"].append({"from": blocking_pid, "to": blocked_pid, "relationship": "blocks"})

            # Analyze blocking chains
            chains = self._find_blocking_chains(blocking_relationships)
            graph["visualization_data"]["blocking_chains"] = chains

            # Find root blockers (processes that block others but aren't blocked)
            root_blockers = []
            for pid in all_pids:
                is_blocker = any(rel[1] == pid for rel in blocking_relationships.items())
                is_blocked = pid in blocking_relationships
                if is_blocker and not is_blocked:
                    root_blockers.append(pid)
            graph["visualization_data"]["root_blockers"] = root_blockers

            # Find leaf blocked (processes that are blocked but don't block others)
            leaf_blocked = []
            for pid in all_pids:
                is_blocked = pid in blocking_relationships
                is_blocker = any(rel[1] == pid for rel in blocking_relationships.items())
                if is_blocked and not is_blocker:
                    leaf_blocked.append(pid)
            graph["visualization_data"]["leaf_blocked"] = leaf_blocked

            return graph

        except Exception as e:
            logger.error(f"Error generating lock wait graph: {e}")
            return {"error": str(e)}

    def _find_blocking_chains(self, blocking_relationships: Dict[int, int]) -> List[List[int]]:
        """Find chains of blocking relationships."""
        chains = []
        visited = set()

        for blocked_pid in blocking_relationships:
            if blocked_pid in visited:
                continue

            chain = []
            current = blocked_pid

            # Follow the chain backwards to find the root
            while current in blocking_relationships:
                if current in chain:  # Circular dependency detected
                    break
                chain.append(current)
                current = blocking_relationships[current]
                visited.add(current)

            if current not in chain:
                chain.append(current)  # Add the root blocker

            if len(chain) > 1:
                chains.append(list(reversed(chain)))  # Reverse to show blocker -> blocked

        return chains

    async def _get_deadlock_analysis(self) -> Dict[str, Any]:
        """Enhanced deadlock detection and analysis."""
        try:
            # Get deadlock settings
            settings_query = """
                SELECT
                    name,
                    setting,
                    unit,
                    category,
                    short_desc
                FROM pg_settings
                WHERE name IN (
                    'deadlock_timeout',
                    'log_lock_waits',
                    'lock_timeout',
                    'statement_timeout',
                    'idle_in_transaction_session_timeout'
                );
            """

            settings_rows = await self.sql_driver.execute_query(settings_query)
            settings = {}
            if settings_rows:
                for row in settings_rows:
                    settings[row.cells["name"]] = {
                        "value": row.cells["setting"],
                        "unit": row.cells["unit"],
                        "category": row.cells["category"],
                        "description": row.cells["short_desc"],
                    }

            # Get database deadlock statistics
            deadlock_stats_query = """
                SELECT
                    datname,
                    deadlocks,
                    temp_files,
                    temp_bytes
                FROM pg_stat_database
                WHERE datname = current_database();
            """

            stats_rows = await self.sql_driver.execute_query(deadlock_stats_query)
            deadlock_stats = {}
            if stats_rows and len(stats_rows) > 0:
                row = stats_rows[0]
                deadlock_stats = {
                    "database": row.cells["datname"],
                    "total_deadlocks": row.cells["deadlocks"],
                    "temp_files": row.cells["temp_files"],
                    "temp_bytes": row.cells["temp_bytes"],
                }

            # Analyze current potential deadlock situations
            potential_deadlocks = await self._detect_potential_deadlocks()

            return {
                "settings": settings,
                "statistics": deadlock_stats,
                "potential_deadlocks": potential_deadlocks,
                "analysis_timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error analyzing deadlocks: {e}")
            return {"error": str(e)}

    async def _detect_potential_deadlocks(self) -> List[Dict[str, Any]]:
        """Detect potential deadlock situations."""
        try:
            # Look for circular wait patterns
            circular_wait_query = """
                WITH RECURSIVE blocking_chain AS (
                    -- Base case: direct blocking relationships
                    SELECT
                        blocked.pid as blocked_pid,
                        blocker.pid as blocking_pid,
                        1 as depth,
                        ARRAY[blocked.pid, blocker.pid] as chain
                    FROM pg_stat_activity blocked
                    JOIN pg_stat_activity blocker ON blocker.pid = ANY(pg_blocking_pids(blocked.pid))
                    WHERE blocked.pid <> pg_backend_pid()

                    UNION ALL

                    -- Recursive case: extend the chain
                    SELECT
                        bc.blocked_pid,
                        blocker.pid as blocking_pid,
                        bc.depth + 1,
                        bc.chain || blocker.pid
                    FROM blocking_chain bc
                    JOIN pg_stat_activity blocker ON blocker.pid = ANY(pg_blocking_pids(bc.blocking_pid))
                    WHERE bc.depth < 10  -- Prevent infinite recursion
                      AND blocker.pid <> ALL(bc.chain)  -- Prevent cycles in recursion
                )
                SELECT DISTINCT
                    blocked_pid,
                    blocking_pid,
                    depth,
                    chain
                FROM blocking_chain
                WHERE blocked_pid = ANY(chain[2:])  -- Circular dependency detected
                ORDER BY depth DESC;
            """

            rows = await self.sql_driver.execute_query(circular_wait_query)
            potential_deadlocks = []

            if rows:
                for row in rows:
                    potential_deadlocks.append(
                        {
                            "blocked_pid": row.cells["blocked_pid"],
                            "blocking_pid": row.cells["blocking_pid"],
                            "chain_depth": row.cells["depth"],
                            "blocking_chain": row.cells["chain"],
                            "risk_level": "HIGH" if row.cells["depth"] > 2 else "MEDIUM",
                        }
                    )

            return potential_deadlocks

        except Exception as e:
            logger.error(f"Error detecting potential deadlocks: {e}")
            return []

    async def _generate_session_termination_recommendations(self, blocking_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate recommendations for which sessions to terminate to resolve blocking."""
        recommendations = []

        try:
            # Analyze blocking impact
            blocker_impact = {}

            for block in blocking_data:
                blocking_pid = block["blocking_process"]["pid"]
                if not blocking_pid:
                    continue

                if blocking_pid not in blocker_impact:
                    blocker_impact[blocking_pid] = {
                        "blocked_sessions": [],
                        "total_wait_time": 0,
                        "blocking_duration": block["blocking_process"]["duration_seconds"],
                        "process_info": block["blocking_process"],
                    }

                blocker_impact[blocking_pid]["blocked_sessions"].append(block["blocked_process"]["pid"])
                blocker_impact[blocking_pid]["total_wait_time"] += block["blocked_process"]["duration_seconds"]

            # Generate termination recommendations
            for blocking_pid, impact in blocker_impact.items():
                priority = "HIGH"
                if impact["total_wait_time"] > 300:  # 5 minutes total wait
                    priority = "CRITICAL"
                elif impact["total_wait_time"] < 60:  # 1 minute total wait
                    priority = "LOW"

                recommendation = {
                    "target_pid": blocking_pid,
                    "priority": priority,
                    "reason": f"Blocking {len(impact['blocked_sessions'])} sessions for {impact['total_wait_time']:.1f} total seconds",
                    "blocked_sessions_count": len(impact["blocked_sessions"]),
                    "total_wait_time": impact["total_wait_time"],
                    "blocking_duration": impact["blocking_duration"],
                    "termination_command": f"SELECT pg_terminate_backend({blocking_pid});",
                    "process_info": {
                        "user": impact["process_info"]["user"],
                        "application": impact["process_info"]["application"],
                        "state": impact["process_info"]["state"],
                    },
                    "impact_assessment": self._assess_termination_impact(impact),
                }

                recommendations.append(recommendation)

            # Sort by priority
            priority_order = {"CRITICAL": 0, "HIGH": 1, "LOW": 2}
            recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))

            return recommendations

        except Exception as e:
            logger.error(f"Error generating session termination recommendations: {e}")
            return []

    def _assess_termination_impact(self, impact: Dict[str, Any]) -> str:
        """Assess the impact of terminating a blocking session."""
        if impact["blocking_duration"] > 1800:  # 30 minutes
            return "LOW_RISK - Long-running session likely stuck"
        elif impact["total_wait_time"] > impact["blocking_duration"] * 2:
            return "MEDIUM_RISK - Blocking multiple sessions significantly"
        else:
            return "HIGH_RISK - Consider alternative solutions first"

    async def _generate_lock_timeout_suggestions(self, blocking_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate optimal lock timeout and statement timeout suggestions."""
        try:
            # Get current timeout settings
            current_settings_query = """
                SELECT name, setting, unit
                FROM pg_settings
                WHERE name IN ('lock_timeout', 'statement_timeout', 'idle_in_transaction_session_timeout');
            """

            rows = await self.sql_driver.execute_query(current_settings_query)
            current_settings = {}
            if rows:
                for row in rows:
                    current_settings[row.cells["name"]] = {"value": row.cells["setting"], "unit": row.cells["unit"]}

            # Analyze wait times to suggest optimal timeouts
            wait_times = [block["blocked_process"]["duration_seconds"] for block in blocking_data]

            if wait_times:
                avg_wait = sum(wait_times) / len(wait_times)
                max_wait = max(wait_times)

                # Suggest lock_timeout based on analysis
                suggested_lock_timeout = min(max(avg_wait * 2, 30), 300)  # Between 30s and 5min

                # Suggest statement_timeout based on blocking patterns
                suggested_statement_timeout = min(max(max_wait * 1.5, 300), 1800)  # Between 5min and 30min

                suggestions = {
                    "current_settings": current_settings,
                    "analysis": {
                        "average_wait_time": avg_wait,
                        "maximum_wait_time": max_wait,
                        "total_blocking_sessions": len(blocking_data),
                    },
                    "recommendations": {
                        "lock_timeout": {
                            "suggested_value": f"{int(suggested_lock_timeout)}s",
                            "reason": f"Based on average wait time of {avg_wait:.1f}s, suggest {int(suggested_lock_timeout)}s to prevent excessive blocking",
                        },
                        "statement_timeout": {
                            "suggested_value": f"{int(suggested_statement_timeout)}s",
                            "reason": f"Based on maximum wait time of {max_wait:.1f}s, suggest {int(suggested_statement_timeout)}s to prevent runaway queries",
                        },
                        "idle_in_transaction_session_timeout": {
                            "suggested_value": "300s",
                            "reason": "Prevent idle transactions from holding locks indefinitely",
                        },
                    },
                }
            else:
                suggestions = {
                    "current_settings": current_settings,
                    "recommendations": {
                        "lock_timeout": {
                            "suggested_value": "60s",
                            "reason": "Standard recommendation for OLTP workloads",
                        },
                        "statement_timeout": {
                            "suggested_value": "600s",
                            "reason": "Standard recommendation to prevent runaway queries",
                        },
                        "idle_in_transaction_session_timeout": {
                            "suggested_value": "300s",
                            "reason": "Prevent idle transactions from holding locks",
                        },
                    },
                }

            return suggestions

        except Exception as e:
            logger.error(f"Error generating lock timeout suggestions: {e}")
            return {"error": str(e)}

    async def _get_historical_blocking_analysis(self) -> Dict[str, Any]:
        """Analyze historical blocking patterns (limited without persistent storage)."""
        try:
            # Since we don't have persistent historical data, we'll analyze current patterns
            # and provide insights based on current session information

            long_running_query = """
                SELECT
                    pid,
                    usename,
                    application_name,
                    state,
                    EXTRACT(EPOCH FROM (now() - backend_start)) as session_duration,
                    EXTRACT(EPOCH FROM (now() - query_start)) as query_duration,
                    EXTRACT(EPOCH FROM (now() - xact_start)) as transaction_duration,
                    query
                FROM pg_stat_activity
                WHERE state IS NOT NULL
                    AND pid <> pg_backend_pid()
                    AND (
                        EXTRACT(EPOCH FROM (now() - backend_start)) > 3600 OR  -- 1 hour sessions
                        EXTRACT(EPOCH FROM (now() - xact_start)) > 1800 OR     -- 30 min transactions
                        EXTRACT(EPOCH FROM (now() - query_start)) > 300        -- 5 min queries
                    )
                ORDER BY session_duration DESC;
            """

            rows = await self.sql_driver.execute_query(long_running_query)
            long_running_sessions = []

            if rows:
                for row in rows:
                    long_running_sessions.append(
                        {
                            "pid": row.cells["pid"],
                            "user": row.cells["usename"],
                            "application": row.cells["application_name"],
                            "state": row.cells["state"],
                            "session_duration": float(row.cells["session_duration"]) if row.cells["session_duration"] else 0,
                            "query_duration": float(row.cells["query_duration"]) if row.cells["query_duration"] else 0,
                            "transaction_duration": float(row.cells["transaction_duration"]) if row.cells["transaction_duration"] else 0,
                            "query": row.cells["query"],
                        }
                    )

            return {
                "long_running_sessions": long_running_sessions,
                "analysis": {
                    "total_long_running": len(long_running_sessions),
                    "potential_blocking_sources": [s for s in long_running_sessions if s["transaction_duration"] > 1800],
                    "recommendations": [
                        "Monitor these long-running sessions as potential blocking sources",
                        "Consider implementing connection pooling to limit session duration",
                        "Review application logic for long-running transactions",
                    ],
                },
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error analyzing historical blocking patterns: {e}")
            return {"error": str(e)}

    async def _detect_lock_escalation(self, blocking_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect when row locks escalate to table locks."""
        try:
            escalation_analysis = {"detected_escalations": [], "risk_factors": [], "recommendations": []}

            # Analyze lock categories for escalation patterns
            table_locks = []
            row_locks = []

            for block in blocking_data:
                lock_categories = block["lock_info"].get("categories", "")
                if "TABLE_LOCK" in lock_categories:
                    table_locks.append(block)
                if "ROW_LOCK" in lock_categories:
                    row_locks.append(block)

            if table_locks:
                escalation_analysis["detected_escalations"] = [
                    {
                        "pid": block["blocked_process"]["pid"],
                        "affected_relations": block["lock_info"]["affected_relations"],
                        "lock_modes": block["lock_info"]["modes"],
                        "escalation_indicator": "Table-level exclusive lock detected",
                    }
                    for block in table_locks
                ]

                escalation_analysis["risk_factors"].extend(
                    [
                        "Large batch operations detected",
                        "Exclusive table locks may indicate lock escalation",
                        "High contention on specific tables",
                    ]
                )

                escalation_analysis["recommendations"].extend(
                    [
                        "Consider breaking large operations into smaller batches",
                        "Review queries for unnecessary table scans",
                        "Implement proper indexing to reduce lock scope",
                    ]
                )

            return escalation_analysis

        except Exception as e:
            logger.error(f"Error detecting lock escalation: {e}")
            return {"error": str(e)}

    async def _analyze_query_patterns(self, blocking_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify queries that frequently cause blocking."""
        try:
            query_patterns = {}

            for block in blocking_data:
                blocking_query = block["blocking_process"]["query"]
                if blocking_query:
                    # Normalize query by removing literals for pattern matching
                    normalized_query = self._normalize_query(blocking_query)

                    if normalized_query not in query_patterns:
                        query_patterns[normalized_query] = {
                            "count": 0,
                            "total_blocking_time": 0,
                            "affected_sessions": [],
                            "example_query": blocking_query,
                        }

                    query_patterns[normalized_query]["count"] += 1
                    query_patterns[normalized_query]["total_blocking_time"] += block["blocking_process"]["duration_seconds"]
                    query_patterns[normalized_query]["affected_sessions"].append(block["blocked_process"]["pid"])

            # Sort by impact (count * average blocking time)
            sorted_patterns = sorted(
                query_patterns.items(),
                key=lambda x: x[1]["count"] * (x[1]["total_blocking_time"] / x[1]["count"]),
                reverse=True,
            )

            analysis = {"problematic_patterns": [], "recommendations": []}

            for pattern, data in sorted_patterns[:5]:  # Top 5 patterns
                avg_blocking_time = data["total_blocking_time"] / data["count"]
                analysis["problematic_patterns"].append(
                    {
                        "pattern": pattern,
                        "frequency": data["count"],
                        "average_blocking_time": avg_blocking_time,
                        "total_impact": data["total_blocking_time"],
                        "example_query": data["example_query"][:200] + "..." if len(data["example_query"]) > 200 else data["example_query"],
                    }
                )

            if analysis["problematic_patterns"]:
                analysis["recommendations"] = [
                    "Focus optimization on the most frequent blocking query patterns",
                    "Consider adding indexes for queries with high blocking frequency",
                    "Review transaction boundaries for long-running operations",
                    "Implement query timeout mechanisms for problematic patterns",
                ]

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing query patterns: {e}")
            return {"error": str(e)}

    def _normalize_query(self, query: str) -> str:
        """Normalize query by removing literals and extra whitespace."""
        import re

        # Remove string literals
        normalized = re.sub(r"'[^']*'", "'?'", query)
        # Remove numeric literals
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized.strip())

        return normalized

    async def _analyze_batch_operation_impact(self, blocking_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze how large operations affect concurrent queries."""
        try:
            batch_indicators = []

            for block in blocking_data:
                blocking_query = block["blocking_process"]["query"]
                if blocking_query:
                    # Look for batch operation indicators
                    batch_keywords = [
                        "INSERT INTO",
                        "UPDATE",
                        "DELETE FROM",
                        "COPY",
                        "CREATE INDEX",
                        "VACUUM",
                        "ANALYZE",
                    ]

                    for keyword in batch_keywords:
                        if keyword in blocking_query.upper():
                            batch_indicators.append(
                                {
                                    "pid": block["blocking_process"]["pid"],
                                    "operation_type": keyword,
                                    "duration": block["blocking_process"]["duration_seconds"],
                                    "blocked_sessions": 1,  # This blocking relationship
                                    "affected_tables": block["lock_info"]["affected_relations"],
                                }
                            )
                            break

            # Aggregate by operation type
            operation_impact = {}
            for indicator in batch_indicators:
                op_type = indicator["operation_type"]
                if op_type not in operation_impact:
                    operation_impact[op_type] = {
                        "total_operations": 0,
                        "total_duration": 0,
                        "total_blocked_sessions": 0,
                        "affected_tables": set(),
                    }

                operation_impact[op_type]["total_operations"] += 1
                operation_impact[op_type]["total_duration"] += indicator["duration"]
                operation_impact[op_type]["total_blocked_sessions"] += indicator["blocked_sessions"]
                if indicator["affected_tables"]:
                    operation_impact[op_type]["affected_tables"].update(indicator["affected_tables"].split(", "))

            # Convert sets to lists for JSON serialization
            for op_data in operation_impact.values():
                op_data["affected_tables"] = list(op_data["affected_tables"])

            return {
                "batch_operations": operation_impact,
                "recommendations": [
                    "Schedule large batch operations during low-activity periods",
                    "Break large operations into smaller chunks with commits",
                    "Use appropriate isolation levels for batch operations",
                    "Monitor and limit concurrent batch operations",
                ]
                if operation_impact
                else [],
            }

        except Exception as e:
            logger.error(f"Error analyzing batch operation impact: {e}")
            return {"error": str(e)}

    async def _get_lock_contention_hotspots(self) -> Dict[str, Any]:
        """Identify specific tables/indexes with frequent lock contention."""
        try:
            hotspot_query = """
                SELECT
                    schemaname,
                    relname,
                    n_tup_ins + n_tup_upd + n_tup_del as total_modifications,
                    n_tup_hot_upd,
                    n_dead_tup,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze
                FROM pg_stat_user_tables
                WHERE n_tup_ins + n_tup_upd + n_tup_del > 1000  -- Tables with significant activity
                ORDER BY total_modifications DESC
                LIMIT 20;
            """

            rows = await self.sql_driver.execute_query(hotspot_query)
            hotspots = []

            if rows:
                for row in rows:
                    hotspots.append(
                        {
                            "schema": row.cells["schemaname"],
                            "table": row.cells["relname"],
                            "total_modifications": row.cells["total_modifications"],
                            "hot_updates": row.cells["n_tup_hot_upd"],
                            "dead_tuples": row.cells["n_dead_tup"],
                            "last_vacuum": row.cells["last_vacuum"],
                            "last_autovacuum": row.cells["last_autovacuum"],
                            "last_analyze": row.cells["last_analyze"],
                            "last_autoanalyze": row.cells["last_autoanalyze"],
                            "contention_risk": "HIGH" if row.cells["total_modifications"] > 10000 else "MEDIUM",
                        }
                    )

            return {
                "contention_hotspots": hotspots,
                "analysis": {
                    "high_risk_tables": len([h for h in hotspots if h["contention_risk"] == "HIGH"]),
                    "total_analyzed": len(hotspots),
                },
                "recommendations": [
                    "Monitor high-activity tables for lock contention",
                    "Ensure regular VACUUM and ANALYZE on busy tables",
                    "Consider partitioning for very large, active tables",
                    "Review indexing strategy for frequently modified tables",
                ]
                if hotspots
                else [],
            }

        except Exception as e:
            logger.error(f"Error identifying lock contention hotspots: {e}")
            return {"error": str(e)}

    def _check_lock_wait_thresholds(self, blocking_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check for configurable alerts for long-running lock waits."""
        alerts = []

        # Configurable thresholds
        thresholds = {
            "WARNING": 60,  # 1 minute
            "CRITICAL": 300,  # 5 minutes
            "EMERGENCY": 900,  # 15 minutes
        }

        for block in blocking_data:
            wait_time = block["blocked_process"]["duration_seconds"]

            for level, threshold in thresholds.items():
                if wait_time >= threshold:
                    alerts.append(
                        {
                            "level": level,
                            "threshold": threshold,
                            "actual_wait_time": wait_time,
                            "blocked_pid": block["blocked_process"]["pid"],
                            "blocking_pid": block["blocking_process"]["pid"],
                            "message": f"{level}: Process {block['blocked_process']['pid']} has been waiting for {wait_time:.1f}s (threshold: {threshold}s)",
                        }
                    )
                    break  # Only add the highest applicable alert level

        return alerts

    async def _generate_healthy_recommendations(self) -> List[str]:
        """Generate recommendations when no blocking is detected."""
        return [
            "✅ No current blocking detected - system is healthy",
            "🔍 Continue monitoring for lock contention patterns",
            "📊 Review query performance regularly using pg_stat_statements",
            "⚙️ Ensure proper indexing on frequently queried tables",
            "🔒 Consider enabling lock monitoring: SET log_lock_waits = on",
            "📈 Monitor deadlock statistics in pg_stat_database",
            "⏱️ Review timeout settings (lock_timeout, statement_timeout)",
            "🧹 Maintain regular VACUUM and ANALYZE schedules",
        ]

    async def _generate_enhanced_recommendations(
        self,
        blocking_data: List[Dict[str, Any]],
        summary: Dict[str, Any],
        session_termination_recs: List[Dict[str, Any]],
        lock_timeout_suggestions: Dict[str, Any],
        historical_analysis: Dict[str, Any],
        lock_escalation_info: Dict[str, Any],
        query_pattern_analysis: Dict[str, Any],
    ) -> List[str]:
        """Generate enhanced recommendations based on comprehensive analysis."""
        recommendations = []

        # Start with basic recommendations
        basic_recs = self._generate_recommendations(blocking_data, summary)
        recommendations.extend(basic_recs)

        # Add session termination recommendations
        if session_termination_recs:
            recommendations.append("\n🎯 SESSION TERMINATION RECOMMENDATIONS:")
            for rec in session_termination_recs[:3]:  # Top 3 recommendations
                recommendations.append(f"   • {rec['priority']}: Terminate PID {rec['target_pid']} - {rec['reason']}")

        # Add timeout suggestions
        if lock_timeout_suggestions.get("recommendations"):
            recommendations.append("\n⏱️ TIMEOUT CONFIGURATION SUGGESTIONS:")
            for setting, config in lock_timeout_suggestions["recommendations"].items():
                recommendations.append(f"   • {setting}: {config['suggested_value']} - {config['reason']}")

        # Add query pattern recommendations
        if query_pattern_analysis.get("problematic_patterns"):
            recommendations.append("\n🔍 QUERY PATTERN ANALYSIS:")
            for pattern in query_pattern_analysis["problematic_patterns"][:2]:  # Top 2 patterns
                recommendations.append(
                    f"   • Optimize pattern with {pattern['frequency']} occurrences (avg blocking: {pattern['average_blocking_time']:.1f}s)"
                )

        # Add lock escalation recommendations
        if lock_escalation_info.get("detected_escalations"):
            recommendations.append("\n🔺 LOCK ESCALATION DETECTED:")
            recommendations.extend([f"   • {rec}" for rec in lock_escalation_info["recommendations"][:2]])

        # Add historical analysis insights
        if historical_analysis.get("analysis", {}).get("potential_blocking_sources"):
            recommendations.append("\n📊 HISTORICAL ANALYSIS:")
            recommendations.append(f"   • {len(historical_analysis['analysis']['potential_blocking_sources'])} long-running sessions detected")

        return recommendations

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
                    lock_summary.append(
                        {
                            "lock_type": row.cells["locktype"],
                            "mode": row.cells["mode"],
                            "granted": row.cells["granted"],
                            "count": row.cells["lock_count"],
                        }
                    )

            return {"lock_summary": lock_summary, "timestamp": datetime.now().isoformat()}
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
                        "category": row.cells["category"],
                    }

            return {"deadlock_settings": settings, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"Error getting deadlock info: {e}")
            raise

    def _generate_recommendations(self, blocking_data: List[Dict[str, Any]], summary: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on blocking query analysis."""
        recommendations = []

        if summary["max_wait_time_seconds"] > 300:  # 5 minutes
            recommendations.append(
                f"CRITICAL: Queries blocked for {summary['max_wait_time_seconds']:.1f}s. Consider terminating long-running blockers."
            )
        elif summary["max_wait_time_seconds"] > 60:  # 1 minute
            recommendations.append(
                f"WARNING: Queries blocked for {summary['max_wait_time_seconds']:.1f}s. Monitor closely and consider intervention."
            )

        if summary["total_blocked"] > 10:
            recommendations.append(f"HIGH CONTENTION: {summary['total_blocked']} queries are blocked. Review query patterns and indexing.")

        # Analyze lock types and patterns from the improved lock_info structure
        lock_types = {}
        for block in blocking_data:
            lock_info_types = block["lock_info"]["types"]
            if lock_info_types:
                for lock_type in lock_info_types.split(", "):
                    lock_types[lock_type] = lock_types.get(lock_type, 0) + 1

        if "transactionid" in lock_types and lock_types["transactionid"] > 3:
            recommendations.append(
                "OPTIMIZATION: Multiple transaction ID locks detected. Shorten transaction duration and avoid long-running transactions."
            )

        if "relation" in lock_types:
            recommendations.append("OPTIMIZATION: Table-level locks detected. Review queries for table scans and consider appropriate indexes.")

        # Check for same relations being blocked multiple times
        if len(summary["affected_relations"]) < summary["total_blocked"] / 2:
            recommendations.append("HOTSPOT: Multiple queries contend for the same tables: " + ", ".join(summary["affected_relations"]))

        # Add recommendations based on wait events
        wait_events = {}
        for block in blocking_data:
            wait_event = block["blocked_process"]["wait_event"]
            if wait_event:
                wait_events[wait_event] = wait_events.get(wait_event, 0) + 1

        if "Lock" in wait_events:
            recommendations.append("LOCK ANALYSIS: High lock contention detected. Consider query optimization, index tuning, or connection pooling.")

        if not recommendations:
            recommendations.append("Status OK: Current blocking appears manageable. Monitor for patterns and trends.")

        return recommendations

    def _format_as_text(self, result: Dict[str, Any]) -> str:
        """Format blocking queries analysis as compact text (no emojis)."""
        out: list[str] = []

        status = result.get("status", "unknown")
        summary = result.get("summary", {})
        blocking_queries = result.get("blocking_queries", [])
        recommendations = result.get("recommendations", [])

        # Status and Summary
        if status == "healthy":
            out.append("Status: healthy")
            out.append(result.get("message", "No blocking queries detected"))
        else:
            line = (
                "Status: blocking_detected "
                f"blocked={summary.get('total_blocked', 0)} "
                f"blocking={summary.get('total_blocking', 0)} "
                f"max_wait={summary.get('max_wait_time_seconds', 0):.1f}s"
            )
            out.append(line)
            if summary.get("affected_relations"):
                out.append("Affected: " + ", ".join(summary.get("affected_relations", [])))
            if summary.get("analysis_timestamp"):
                out.append(f"Time: {summary.get('analysis_timestamp')}")

        # Blocking queries details (condensed)
        if blocking_queries:
            for i, block in enumerate(blocking_queries, 1):
                bp = block.get("blocked_process", {})
                bl = block.get("blocking_process", {})
                li = block.get("lock_info", {})

                # Blocked line
                q = bp.get("query", "") or ""
                q = (q[:100] + "...") if len(q) > 100 else q
                out.append(
                    f"{i}. Blocked pid={bp.get('pid', 'NA')} user={bp.get('user', 'NA')} app={bp.get('application', 'NA')} "
                    f"state={bp.get('state', 'NA')} wait={bp.get('duration_seconds', 0):.1f}s event={bp.get('wait_event', 'NA')} type={bp.get('wait_event_type', 'NA')}"
                )
                if q:
                    out.append("   q: " + q)

                # Blocking process
                if bl.get("pid"):
                    bq = bl.get("query", "") or ""
                    bq = (bq[:100] + "...") if len(bq) > 100 else bq
                    out.append(
                        f"   Blocking pid={bl.get('pid', 'NA')} user={bl.get('user', 'NA')} state={bl.get('state', 'NA')} dur={bl.get('duration_seconds', 0):.1f}s"
                    )
                    if bq:
                        out.append("   bq: " + bq)

                # Locks
                if li:
                    parts = []
                    if li.get("types"):
                        parts.append(f"types={li.get('types')}")
                    if li.get("modes"):
                        parts.append(f"modes={li.get('modes')}")
                    if li.get("count"):
                        parts.append(f"count={li.get('count')}")
                    if li.get("affected_relations"):
                        parts.append(f"rels={li.get('affected_relations')}")
                    if parts:
                        out.append("   Locks: " + "; ".join(parts))

                # Blocking hierarchy
                hier = block.get("blocking_hierarchy", {})
                pids = hier.get("all_blocking_pids", [])
                if pids and len(pids) > 1:
                    out.append(f"   Hier: all=[{', '.join(map(str, pids))}] immediate={hier.get('immediate_blocker', 'NA')}")

        # Recommendations (single line list)
        if recommendations:
            out.append("Recs: " + " | ".join(recommendations))

        # Healthy notes
        if status == "healthy":
            out.append("Notes: no blocking; queries running without lock contention; locking normal")
            out.append("Monitor: watch contention patterns; review performance; enable lock monitoring; check deadlocks logs")

        return "\n".join(out)
