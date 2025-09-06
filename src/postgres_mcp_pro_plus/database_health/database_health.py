from __future__ import annotations

import logging
from enum import Enum
from typing import List

import mcp.types as types

from .buffer_health_calc import BufferHealthCalc
from .connection_health_calc import ConnectionHealthCalc
from .constraint_health_calc import ConstraintHealthCalc
from .index_health_calc import IndexHealthCalc
from .replication_calc import ReplicationCalc
from .sequence_health_calc import SequenceHealthCalc
from .vacuum_health_calc import VacuumHealthCalc

ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

logger = logging.getLogger(__name__)


class HealthType(str, Enum):
    INDEX = "index"
    CONNECTION = "connection"
    VACUUM = "vacuum"
    SEQUENCE = "sequence"
    REPLICATION = "replication"
    BUFFER = "buffer"
    CONSTRAINT = "constraint"
    ALL = "all"


class DatabaseHealthTool:
    """Tool for analyzing database health metrics."""

    def __init__(self, sql_driver):
        self.sql_driver = sql_driver

    async def health(self, health_type: str) -> str:
        """Run database health checks and return compact, labeled results."""
        try:

            def compact(label: str, text: str) -> str:
                # Join lines, strip bullets and excess spaces
                lines = [ln.strip().lstrip("- •") for ln in text.splitlines() if ln.strip()]
                return f"{label}: " + ("; ".join(lines) if lines else "(none)")

            try:
                health_types = {HealthType(x.strip()) for x in health_type.split(",")}
            except ValueError:
                return f"Invalid health types: '{health_type}'. Valid: " + ", ".join(sorted([t.value for t in HealthType]))

            if HealthType.ALL in health_types:
                health_types = [t.value for t in HealthType if t != HealthType.ALL]

            out: list[str] = []

            if HealthType.INDEX in health_types:
                index_health = IndexHealthCalc(self.sql_driver)
                out.append(compact("index.invalid", await index_health.invalid_index_check()))
                out.append(compact("index.duplicate", await index_health.duplicate_index_check()))
                out.append(compact("index.bloat", await index_health.index_bloat()))
                out.append(compact("index.unused", await index_health.unused_indexes()))

            if HealthType.CONNECTION in health_types:
                connection_health = ConnectionHealthCalc(self.sql_driver)
                out.append(compact("connection", await connection_health.connection_health_check()))

            if HealthType.VACUUM in health_types:
                vacuum_health = VacuumHealthCalc(self.sql_driver)
                out.append(compact("vacuum.txid", await vacuum_health.transaction_id_danger_check()))

            if HealthType.SEQUENCE in health_types:
                sequence_health = SequenceHealthCalc(self.sql_driver)
                out.append(compact("sequence", await sequence_health.sequence_danger_check()))

            if HealthType.REPLICATION in health_types:
                replication_health = ReplicationCalc(self.sql_driver)
                out.append(compact("replication", await replication_health.replication_health_check()))

            if HealthType.BUFFER in health_types:
                buffer_health = BufferHealthCalc(self.sql_driver)
                out.append(compact("buffer.index_hit", await buffer_health.index_hit_rate()))
                out.append(compact("buffer.table_hit", await buffer_health.table_hit_rate()))

            if HealthType.CONSTRAINT in health_types:
                constraint_health = ConstraintHealthCalc(self.sql_driver)
                out.append(compact("constraint", await constraint_health.invalid_constraints_check()))

            return "\n".join([line for line in out if line]) if out else "No health checks performed"
        except Exception as e:
            logger.error(f"Error calculating database health: {e}", exc_info=True)
            return f"Error calculating database health: {e}"
