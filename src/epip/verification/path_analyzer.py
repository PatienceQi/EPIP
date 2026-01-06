"""Reasoning path analysis helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from epip.verification.trace import ReasoningTrace


@dataclass(slots=True)
class PathAnalysis:
    """Aggregated diagnostics for a reasoning trace."""

    path_length: int
    branch_points: list[str]
    weak_points: list[str]
    quality_score: float
    bottlenecks: list[str]


class PathAnalyzer:
    """Provides utility methods to evaluate reasoning traces."""

    def analyze(self, trace: ReasoningTrace) -> PathAnalysis:
        """High-level entry point that summarizes several metrics."""

        adjacency = self._build_adjacency(trace)
        branch_points = [node_id for node_id, targets in adjacency.items() if len(targets) > 1]
        weak_points = self.find_weak_points(trace)
        bottlenecks = self._identify_bottlenecks(trace, adjacency)
        quality_score = self.calculate_quality(trace)
        path_length = len(trace.critical_path) if trace.critical_path else trace.total_steps
        return PathAnalysis(
            path_length=path_length,
            branch_points=branch_points,
            weak_points=weak_points,
            quality_score=quality_score,
            bottlenecks=bottlenecks,
        )

    def find_weak_points(self, trace: ReasoningTrace, threshold: float = 0.7) -> list[str]:
        """Return nodes on the critical path whose confidence is below ``threshold``."""

        if not trace.nodes:
            return []

        normalized_threshold = max(0.0, min(1.0, threshold))
        path_scope = set(trace.critical_path or [node.node_id for node in trace.nodes])
        weak_points = [
            node.node_id
            for node in trace.nodes
            if node.node_id in path_scope and node.confidence < normalized_threshold
        ]
        return weak_points

    def calculate_quality(self, trace: ReasoningTrace) -> float:
        """Compute a simple quality score that balances confidence and coverage."""

        if not trace.nodes:
            return 0.0

        avg_confidence = max(0.0, min(1.0, trace.avg_confidence))
        path_coverage = (
            len(trace.critical_path) / trace.total_steps if trace.total_steps else avg_confidence
        )
        contradiction_penalty = min(
            0.5, sum(1 for edge in trace.edges if edge.edge_type == "contradicts") * 0.1
        )
        quality = (0.7 * avg_confidence) + (0.3 * path_coverage) - contradiction_penalty
        return max(0.0, min(1.0, quality))

    def suggest_improvements(self, analysis: PathAnalysis) -> list[str]:
        """Provide actionable hints based on the path analysis."""

        suggestions: list[str] = []
        if analysis.weak_points:
            weak_listing = ", ".join(analysis.weak_points)
            suggestions.append(f"Boost evidence for low-confidence nodes: {weak_listing}.")
        if analysis.branch_points:
            suggestions.append(
                "Review branching decisions to ensure each path has supporting evidence."
            )
        if analysis.quality_score < 0.6:
            suggestions.append("Collect additional observations to improve the path quality score.")
        if analysis.bottlenecks:
            bottleneck_listing = ", ".join(analysis.bottlenecks)
            suggestions.append(f"Resolve bottlenecks around nodes: {bottleneck_listing}.")
        if not suggestions:
            suggestions.append("Reasoning path is stable; continue monitoring for drift.")
        return suggestions

    @staticmethod
    def _build_adjacency(trace: ReasoningTrace) -> dict[str, list[str]]:
        adjacency: dict[str, list[str]] = {node.node_id: [] for node in trace.nodes}
        for edge in trace.edges:
            if edge.source_id in adjacency and edge.target_id in adjacency:
                adjacency[edge.source_id].append(edge.target_id)
        return adjacency

    def _identify_bottlenecks(
        self,
        trace: ReasoningTrace,
        adjacency: dict[str, list[str]],
    ) -> list[str]:
        if not trace.critical_path:
            return []

        incoming_counts: dict[str, int] = defaultdict(int)
        for edge in trace.edges:
            incoming_counts[edge.target_id] += 1

        node_map = {node.node_id: node for node in trace.nodes}
        bottlenecks: list[str] = []
        for node_id in trace.critical_path:
            node = node_map.get(node_id)
            if not node:
                continue
            indegree = incoming_counts.get(node_id, 0)
            outdegree = len(adjacency.get(node_id, []))
            if (indegree + outdegree) > 2 and node.confidence < 0.75:
                bottlenecks.append(node_id)
        return bottlenecks
