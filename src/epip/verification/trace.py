"""Reasoning trace data structures and recorder utilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isclose
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_NODE_TYPES = {"thought", "action", "observation", "conclusion"}
_EDGE_TYPES = {"leads_to", "supports", "contradicts"}


@dataclass(slots=True)
class TraceNode:
    """Representation of a reasoning step collected during verification."""

    node_id: str
    node_type: str
    content: str
    confidence: float
    timestamp: datetime
    kg_references: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TraceEdge:
    """Directed relation between two reasoning nodes."""

    source_id: str
    target_id: str
    edge_type: str
    weight: float


@dataclass(slots=True)
class ReasoningTrace:
    """Snapshot of a completed reasoning pass."""

    trace_id: str
    query: str
    nodes: list[TraceNode]
    edges: list[TraceEdge]
    critical_path: list[str]
    total_steps: int
    avg_confidence: float


class TraceRecorder:
    """Helper that records reasoning nodes and edges for later inspection."""

    def __init__(
        self,
        *,
        node_id_factory: Callable[[int], str] | None = None,
        trace_id_factory: Callable[[int], str] | None = None,
        time_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._nodes: list[TraceNode] = []
        self._edges: list[TraceEdge] = []
        self._node_index: dict[str, TraceNode] = {}
        self._node_counter = 0
        self._trace_counter = 0
        self._node_id_factory = node_id_factory or (lambda index: f"node-{index}")
        self._trace_id_factory = trace_id_factory or (lambda index: f"trace-{index}")
        self._time_provider = time_provider or (lambda: datetime.now(UTC))

    def record_node(
        self,
        node_type: str,
        content: str,
        confidence: float,
        kg_refs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Record a reasoning node and return its identifier."""

        normalized_type = node_type.strip().lower()
        if normalized_type not in _NODE_TYPES:
            raise ValueError(f"Unsupported node_type '{node_type}'.")

        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Node content cannot be empty.")

        bounded_confidence = float(max(0.0, min(1.0, confidence)))
        self._node_counter += 1
        node_id = self._node_id_factory(self._node_counter)
        references = list(dict.fromkeys(kg_refs or []))
        node = TraceNode(
            node_id=node_id,
            node_type=normalized_type,
            content=normalized_content,
            confidence=bounded_confidence,
            timestamp=self._time_provider(),
            kg_references=references,
            metadata=dict(metadata) if metadata else {},
        )
        self._nodes.append(node)
        self._node_index[node_id] = node
        return node_id

    def record_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0,
    ) -> None:
        """Record a relation between existing nodes."""

        if source_id not in self._node_index:
            raise ValueError(f"Unknown source node '{source_id}'.")
        if target_id not in self._node_index:
            raise ValueError(f"Unknown target node '{target_id}'.")

        normalized_type = edge_type.strip().lower()
        if normalized_type not in _EDGE_TYPES:
            raise ValueError(f"Unsupported edge_type '{edge_type}'.")

        self._edges.append(
            TraceEdge(
                source_id=source_id,
                target_id=target_id,
                edge_type=normalized_type,
                weight=float(weight),
            )
        )

    def build_trace(self, query: str) -> ReasoningTrace:
        """Return the complete reasoning trace for ``query``."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Query cannot be empty when building a trace.")

        critical_path = self.find_critical_path()
        total_steps = len(self._nodes)
        avg_confidence = (
            sum(node.confidence for node in self._nodes) / total_steps if total_steps else 0.0
        )

        self._trace_counter += 1
        trace_id = self._trace_id_factory(self._trace_counter)
        return ReasoningTrace(
            trace_id=trace_id,
            query=normalized_query,
            nodes=list(self._nodes),
            edges=list(self._edges),
            critical_path=critical_path,
            total_steps=total_steps,
            avg_confidence=avg_confidence,
        )

    def find_critical_path(self) -> list[str]:
        """Return the path of nodes that carries the strongest combined signal."""

        if not self._nodes:
            return []

        adjacency: dict[str, list[TraceEdge]] = {node.node_id: [] for node in self._nodes}
        incoming_counts: dict[str, int] = {node.node_id: 0 for node in self._nodes}
        for edge in self._edges:
            if edge.source_id not in adjacency or edge.target_id not in adjacency:
                continue
            adjacency[edge.source_id].append(edge)
            incoming_counts[edge.target_id] += 1

        start_nodes = [node_id for node_id, count in incoming_counts.items() if count == 0]
        if not start_nodes:
            start_nodes = [self._nodes[0].node_id]

        cache: dict[str, tuple[float, list[str]]] = {}

        def dfs(node_id: str, stack: set[str]) -> tuple[float, list[str]]:
            if node_id in cache:
                return cache[node_id]

            node = self._node_index[node_id]
            base_score = node.confidence
            best_score = base_score
            best_path = [node_id]
            stack.add(node_id)
            for edge in adjacency.get(node_id, []):
                target = edge.target_id
                if target in stack:
                    continue
                score, path = dfs(target, stack)
                candidate_score = base_score + edge.weight + score
                if candidate_score > best_score or (
                    isclose(candidate_score, best_score, rel_tol=1e-9, abs_tol=1e-12)
                    and len(path) + 1 > len(best_path)
                ):
                    best_score = candidate_score
                    best_path = [node_id, *path]
            stack.remove(node_id)
            cache[node_id] = (best_score, best_path)
            return cache[node_id]

        overall_path: list[str] = []
        overall_score = float("-inf")
        for start in start_nodes:
            score, path = dfs(start, set())
            if score > overall_score or (
                isclose(score, overall_score, rel_tol=1e-9, abs_tol=1e-12)
                and len(path) > len(overall_path)
            ):
                overall_score = score
                overall_path = path
        return overall_path
