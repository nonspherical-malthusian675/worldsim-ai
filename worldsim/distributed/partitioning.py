"""Spatial partitioning and load balancing for distributed simulation."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SpatialRegion:
    """A rectangular region of the simulation grid."""
    region_id: int = 0
    min_x: float = 0.0
    max_x: float = 0.0
    min_y: float = 0.0
    max_y: float = 0.0
    assigned_node: int = 0


class SpatialPartitioner:
    """Divides the world grid into regions and assigns agents to nodes.

    Uses spatial hashing for efficient neighbor lookup.
    """

    def __init__(self, world_width: float = 1000.0, world_height: float = 1000.0) -> None:
        self.world_width = world_width
        self.world_height = world_height

    def partition(self, num_nodes: int) -> List[SpatialRegion]:
        """Create spatial regions for the given number of nodes."""
        if num_nodes <= 0:
            return []

        cols = math.ceil(math.sqrt(num_nodes))
        rows = math.ceil(num_nodes / cols)
        cell_w = self.world_width / cols
        cell_h = self.world_height / rows

        regions: List[SpatialRegion] = []
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx >= num_nodes:
                    break
                regions.append(SpatialRegion(
                    region_id=idx,
                    min_x=c * cell_w, max_x=(c + 1) * cell_w,
                    min_y=r * cell_h, max_y=(r + 1) * cell_h,
                    assigned_node=idx,
                ))
                idx += 1
        return regions

    def assign_agents_to_nodes(
        self,
        agents: List[Any],
        num_nodes: int,
    ) -> Dict[int, List[str]]:
        """Assign agents to nodes based on spatial partitioning.

        Args:
            agents: List of objects with ``agent_id`` and ``position`` (list/tuple of [x, y]).
            num_nodes: Number of nodes to distribute across.

        Returns:
            Mapping of node_id -> list of agent_ids.
        """
        regions = self.partition(num_nodes)
        if not regions:
            return {0: [getattr(a, "agent_id", str(i)) for i, a in enumerate(agents)]}

        assignments: Dict[int, List[str]] = {i: [] for i in range(num_nodes)}
        for agent in agents:
            aid = getattr(agent, "agent_id", str(agent))
            pos = getattr(agent, "position", [0.0, 0.0])
            x, y = float(pos[0]) if len(pos) > 0 else 0.0, float(pos[1]) if len(pos) > 1 else 0.0

            assigned = 0
            for region in regions:
                if region.min_x <= x < region.max_x and region.min_y <= y < region.max_y:
                    assigned = region.assigned_node
                    break
            assignments.setdefault(assigned, []).append(aid)

        return assignments

    def spatial_hash(self, x: float, y: float, cell_size: float = 50.0) -> int:
        """Compute spatial hash for a point."""
        return int(x // cell_size) * 73856093 ^ int(y // cell_size) * 19349663

    def find_neighbors(
        self,
        x: float, y: float,
        agents: List[Any],
        radius: float = 50.0,
    ) -> List[Any]:
        """Find agents within a radius using spatial hashing."""
        cell_size = radius
        nearby: List[Any] = []
        for agent in agents:
            pos = getattr(agent, "position", [0.0, 0.0])
            ax, ay = float(pos[0]) if len(pos) > 0 else 0.0, float(pos[1]) if len(pos) > 1 else 0.0
            if abs(x - ax) <= radius and abs(y - ay) <= radius:
                dist = math.sqrt((x - ax) ** 2 + (y - ay) ** 2)
                if dist <= radius:
                    nearby.append(agent)
        return nearby


# ---------------------------------------------------------------------------
# Load Balancer
# ---------------------------------------------------------------------------

@dataclass
class NodeLoad:
    node_id: int = 0
    agent_count: int = 0
    cpu_load: float = 0.0
    memory_mb: float = 0.0


@dataclass
class RebalancingPlan:
    migrations: List[Tuple[int, int, List[str]]] = field(default_factory=list)  # (src, dst, agent_ids)


class LoadBalancer:
    """Rebalances agents across nodes when load is uneven."""

    def __init__(self, max_imbalance_ratio: float = 1.5) -> None:
        self.max_imbalance_ratio = max_imbalance_ratio

    def monitor_load(self, nodes: List[NodeLoad]) -> List[NodeLoad]:
        """Return current load info (placeholder for real monitoring)."""
        return nodes

    def compute_rebalancing_plan(
        self,
        nodes: List[NodeLoad],
        agent_assignments: Dict[int, List[str]],
    ) -> RebalancingPlan:
        """Compute a plan to rebalance agents if nodes are unevenly loaded."""
        if not nodes:
            return RebalancingPlan()

        total_agents = sum(n.agent_count for n in nodes)
        if total_agents == 0:
            return RebalancingPlan()

        avg = total_agents / len(nodes)
        threshold = avg * self.max_imbalance_ratio

        plan = RebalancingPlan()
        overloaded = sorted([n for n in nodes if n.agent_count > threshold], key=lambda n: -n.agent_count)
        underloaded = sorted([n for n in nodes if n.agent_count < avg * 0.8], key=lambda n: n.agent_count)

        src_idx = 0
        dst_idx = 0
        while src_idx < len(overloaded) and dst_idx < len(underloaded):
            src = overloaded[src_idx]
            dst = underloaded[dst_idx]
            excess = src.agent_count - int(avg)
            capacity = int(avg) - dst.agent_count
            if excess <= 0 or capacity <= 0:
                break

            migrate_count = min(excess, capacity)
            agents = agent_assignments.get(src.node_id, [])[:migrate_count]
            if agents:
                plan.migrations.append((src.node_id, dst.node_id, agents))
                src.agent_count -= migrate_count
                dst.agent_count += migrate_count
            src_idx += 1
            dst_idx += 1

        return plan

    def apply_migration(
        self,
        source_node: int,
        target_node: int,
        agent_ids: List[str],
        agent_assignments: Dict[int, List[str]],
    ) -> Dict[int, List[str]]:
        """Apply a migration, updating the assignment map."""
        for aid in agent_ids:
            if aid in agent_assignments.get(source_node, []):
                agent_assignments[source_node].remove(aid)
                agent_assignments.setdefault(target_node, []).append(aid)
        return agent_assignments
