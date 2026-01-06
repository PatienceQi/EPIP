"""Utilities for generating visualization-friendly graph data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from epip.verification.report import VerificationReport
from epip.verification.trace import ReasoningTrace


@dataclass(slots=True)
class VisNode:
    """Serializable representation of a visualization node."""

    id: str
    label: str
    type: str
    confidence: float
    color: str
    size: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VisEdge:
    """Serializable representation of a visualization edge."""

    source: str
    target: str
    label: str
    weight: float
    color: str


@dataclass(slots=True)
class VisGraph:
    """Complete graph payload consumed by D3 visualizations."""

    nodes: list[VisNode] = field(default_factory=list)
    edges: list[VisEdge] = field(default_factory=list)
    layout: str = "force"


class VisualizationDataGenerator:
    """Transforms verification artifacts into D3 compatible graphs."""

    def __init__(self, *, base_node_size: int = 26) -> None:
        self._base_node_size = base_node_size
        self._edge_colors = {
            "supports": "#2e7d32",
            "leads_to": "#1565c0",
            "contradicts": "#c62828",
            "evidence": "#5d4037",
            "conflict": "#b71c1c",
            "default": "#90a4ae",
        }
        self._type_colors = {
            "thought": "#3949ab",
            "action": "#00838f",
            "observation": "#6a1b9a",
            "conclusion": "#ef6c00",
            "answer": "#283593",
            "fact": "#0277bd",
            "evidence": "#455a64",
            "conflict": "#b71c1c",
        }

    def from_trace(self, trace: ReasoningTrace) -> VisGraph:
        """Convert a reasoning trace into a visual graph."""

        critical = set(trace.critical_path)
        nodes: list[VisNode] = []
        for node in trace.nodes:
            highlighted = node.node_id in critical
            metadata = {
                "node_type": node.node_type,
                "critical": highlighted,
                "kg_references": list(node.kg_references),
                "timestamp": node.timestamp.isoformat(),
                "type_color": self._node_type_to_color(node.node_type),
            }
            if node.metadata:
                metadata.update(node.metadata)
            nodes.append(
                VisNode(
                    id=node.node_id,
                    label=node.content,
                    type=node.node_type,
                    confidence=float(node.confidence),
                    color=self._confidence_to_color(node.confidence),
                    size=self._node_size(node.confidence, highlighted),
                    metadata=metadata,
                )
            )

        edges: list[VisEdge] = []
        for edge in trace.edges:
            edges.append(
                VisEdge(
                    source=edge.source_id,
                    target=edge.target_id,
                    label=edge.edge_type,
                    weight=float(edge.weight),
                    color=self._edge_colors.get(edge.edge_type, self._edge_colors["default"]),
                )
            )
        return VisGraph(nodes=nodes, edges=edges)

    def from_verification(self, report: VerificationReport) -> VisGraph:
        """Convert a verification report into a visual graph."""

        nodes: list[VisNode] = []
        edges: list[VisEdge] = []
        root_id = f"answer:{report.answer_id}"
        status_color_map = {
            "verified": self._edge_colors["supports"],
            "partial": self._edge_colors["leads_to"],
            "unverified": self._edge_colors["default"],
            "contradicted": self._edge_colors["contradicts"],
        }
        nodes.append(
            VisNode(
                id=root_id,
                label=f"Answer {report.answer_id}",
                type="answer",
                confidence=float(report.overall_confidence),
                color=self._confidence_to_color(report.overall_confidence),
                size=self._node_size(report.overall_confidence, True),
                metadata={
                    "total_facts": report.total_facts,
                    "verified": report.verified_count,
                    "partial": report.partial_count,
                    "unverified": report.unverified_count,
                    "contradicted": report.contradicted_count,
                    "type_color": self._node_type_to_color("answer"),
                },
            )
        )

        for result in report.results:
            fact = result.fact
            fact_id = f"fact:{fact.fact_id}"
            fact_metadata = {
                "status": result.status.value,
                "fact_id": fact.fact_id,
                "fact_type": fact.fact_type.value,
                "subject": fact.subject,
                "predicate": fact.predicate,
                "object": fact.object,
                "evidence_count": len(result.evidences),
                "conflict_count": len(result.conflicts),
                "explanation": result.explanation,
                "type_color": self._node_type_to_color("fact"),
            }
            nodes.append(
                VisNode(
                    id=fact_id,
                    label=fact.content,
                    type="fact",
                    confidence=float(result.confidence),
                    color=self._confidence_to_color(result.confidence),
                    size=self._node_size(result.confidence),
                    metadata=fact_metadata,
                )
            )
            edges.append(
                VisEdge(
                    source=root_id,
                    target=fact_id,
                    label=result.status.value,
                    weight=float(max(result.confidence, 0.2)),
                    color=status_color_map.get(result.status.value, self._edge_colors["default"]),
                )
            )

            for idx, evidence in enumerate(result.evidences, start=1):
                evidence_id = f"evidence:{fact.fact_id}:{idx}"
                nodes.append(
                    VisNode(
                        id=evidence_id,
                        label=evidence.content,
                        type="evidence",
                        confidence=float(evidence.confidence),
                        color=self._confidence_to_color(max(evidence.confidence, 0.0)),
                        size=max(int(self._base_node_size * 0.8), 14),
                        metadata={
                            "source_id": evidence.source_id,
                            "source_type": evidence.source_type,
                            "type_color": self._node_type_to_color("evidence"),
                        },
                    )
                )
                edges.append(
                    VisEdge(
                        source=fact_id,
                        target=evidence_id,
                        label="evidence",
                        weight=float(max(evidence.confidence, 0.1)),
                        color=self._edge_colors.get("evidence", self._edge_colors["default"]),
                    )
                )

            for idx, conflict in enumerate(result.conflicts, start=1):
                conflict_id = f"conflict:{fact.fact_id}:{idx}"
                nodes.append(
                    VisNode(
                        id=conflict_id,
                        label=conflict.content,
                        type="conflict",
                        confidence=float(conflict.confidence),
                        color=self._node_type_to_color("conflict"),
                        size=max(int(self._base_node_size * 0.8), 14),
                        metadata={
                            "source_id": conflict.source_id,
                            "source_type": conflict.source_type,
                            "type_color": self._node_type_to_color("conflict"),
                        },
                    )
                )
                edges.append(
                    VisEdge(
                        source=fact_id,
                        target=conflict_id,
                        label="conflict",
                        weight=float(max(conflict.confidence, 0.1)),
                        color=self._edge_colors.get("conflict", self._edge_colors["default"]),
                    )
                )
        return VisGraph(nodes=nodes, edges=edges)

    def _confidence_to_color(self, confidence: float) -> str:
        """Map confidence in [0,1] to a red-yellow-green gradient."""

        value = max(0.0, min(1.0, float(confidence)))
        if value <= 0.5:
            ratio = value / 0.5
            start = (214, 28, 43)
            end = (242, 192, 55)
        else:
            ratio = (value - 0.5) / 0.5
            start = (242, 192, 55)
            end = (25, 169, 116)
        red = int(start[0] + (end[0] - start[0]) * ratio)
        green = int(start[1] + (end[1] - start[1]) * ratio)
        blue = int(start[2] + (end[2] - start[2]) * ratio)
        return f"#{red:02x}{green:02x}{blue:02x}"

    def _node_type_to_color(self, node_type: str) -> str:
        """Map logical node type to a consistent accent color."""

        normalized = node_type.lower().strip()
        return self._type_colors.get(normalized, self._edge_colors["default"])

    def _node_size(self, confidence: float, highlighted: bool = False) -> int:
        value = self._base_node_size + int(max(0.0, min(1.0, confidence)) * 12)
        return int(value * 1.2) if highlighted else value

    def to_d3_json(self, graph: VisGraph) -> dict[str, Any]:
        """Return a JSON-serializable structure for D3 visualizations."""

        return {
            "layout": graph.layout,
            "nodes": [
                {
                    "id": node.id,
                    "label": node.label,
                    "type": node.type,
                    "confidence": node.confidence,
                    "color": node.color,
                    "size": node.size,
                    "metadata": node.metadata,
                }
                for node in graph.nodes
            ],
            "links": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "label": edge.label,
                    "weight": edge.weight,
                    "color": edge.color,
                }
                for edge in graph.edges
            ],
            "stats": {"nodes": len(graph.nodes), "edges": len(graph.edges)},
        }


__all__ = [
    "VisNode",
    "VisEdge",
    "VisGraph",
    "VisualizationDataGenerator",
]
