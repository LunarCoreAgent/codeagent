"""Blueprint graph: a DAG of agent/manager/slot/condition/approval/aggregate nodes.

Inspired by HiveWard's blueprint canvas: instead of a fixed pipeline, the
workflow is a free-form directed acyclic graph. Upstream outputs flow into
downstream nodes along edges; conditions and managers decide which branches
activate; approvals pause for a human decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeKind(str, Enum):
    AGENT = "agent"          # LLM executes a task with upstream outputs as input
    MANAGER = "manager"      # LLM reads upstream results, picks downstream branches
    SLOT = "slot"            # parallel execution line (fan-out worker)
    CONDITION = "condition"  # LLM picks exactly one downstream branch
    APPROVAL = "approval"    # human gate: approve / reject / reply
    AGGREGATE = "aggregate"  # merge all upstream outputs into one
    # HomeRail-style runtime primitives
    JOIN = "join"            # admission gate: all / any / n_of_m upstream quorum
    LOOP = "loop"            # repeat own task N times, collecting every result
    WHILE = "while"          # repeat own task while LLM says continue (bounded)
    COMMAND = "command"      # execute an allowlisted argv (no shell)


@dataclass(frozen=True)
class Node:
    id: str
    kind: NodeKind
    label: str = ""
    prompt: str = ""  # task template; may contain {task} and {inputs}
    config: dict[str, Any] = field(default_factory=dict)
    # join:    mode=all|any|n_of_m, threshold=int
    # loop:    max_iterations=int
    # while:   max_iterations=int
    # command: argv=list[str]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("node id must not be empty")


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str = ""  # branch name; conditions/managers reference these


class CycleError(ValueError):
    """Raised when the blueprint graph contains a cycle."""


class Blueprint:
    """A validated DAG of nodes and edges."""

    def __init__(
        self,
        nodes: list[Node],
        edges: list[Edge],
        name: str = "blueprint",
    ) -> None:
        self.name = name
        self.nodes: dict[str, Node] = {}
        for node in nodes:
            if node.id in self.nodes:
                raise ValueError(f"duplicate node id: {node.id!r}")
            self.nodes[node.id] = node
        self.edges = list(edges)
        self._validate()

    def _validate(self) -> None:
        for edge in self.edges:
            if edge.source not in self.nodes:
                raise ValueError(f"edge source {edge.source!r} is not a node")
            if edge.target not in self.nodes:
                raise ValueError(f"edge target {edge.target!r} is not a node")
        self._topo_order()  # raises CycleError if cyclic

    def upstream(self, node_id: str) -> list[str]:
        return [e.source for e in self.edges if e.target == node_id]

    def downstream(self, node_id: str) -> list[str]:
        return [e.target for e in self.edges if e.source == node_id]

    def downstream_edges(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id]

    def roots(self) -> list[str]:
        return [n for n in self.nodes if not self.upstream(n)]

    def leaves(self) -> list[str]:
        return [n for n in self.nodes if not self.downstream(n)]

    def _topo_order(self) -> list[str]:
        indegree = {n: 0 for n in self.nodes}
        for edge in self.edges:
            indegree[edge.target] += 1
        queue = [n for n, d in indegree.items() if d == 0]
        order: list[str] = []
        while queue:
            current = queue.pop()
            order.append(current)
            for nxt in self.downstream(current):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if len(order) != len(self.nodes):
            raise CycleError(f"blueprint {self.name!r} contains a cycle")
        return order

    def topo_levels(self) -> list[list[str]]:
        """Group node ids into parallel-executable topological levels."""
        indegree = {n: 0 for n in self.nodes}
        for edge in self.edges:
            indegree[edge.target] += 1
        level = [n for n, d in indegree.items() if d == 0]
        levels: list[list[str]] = []
        while level:
            levels.append(level)
            nxt: list[str] = []
            for node_id in level:
                for target in self.downstream(node_id):
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        nxt.append(target)
            level = nxt
        return levels
