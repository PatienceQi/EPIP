"""Visualization-focused FastAPI routes."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from epip.verification.report import VerificationReport
from epip.verification.trace import ReasoningTrace
from epip.visualization import VisualizationDataGenerator

router = APIRouter(prefix="/api/visualization", tags=["visualization"])


class VisualizationMemoryStore:
    """In-memory store used to expose reasoning artifacts via the API."""

    def __init__(self) -> None:
        self._traces: dict[str, ReasoningTrace] = {}
        self._reports: dict[str, VerificationReport] = {}

    def clear(self) -> None:
        self._traces.clear()
        self._reports.clear()

    def set_trace(self, trace: ReasoningTrace) -> None:
        self._traces[trace.trace_id] = trace

    def set_report(self, report: VerificationReport) -> None:
        self._reports[report.answer_id] = report

    async def get_trace(self, trace_id: str) -> ReasoningTrace | None:
        return self._traces.get(trace_id)

    async def get_report(self, answer_id: str) -> VerificationReport | None:
        return self._reports.get(answer_id)

    async def get_node_context(self, node_id: str) -> dict[str, Any] | None:
        for trace in self._traces.values():
            node = next((node for node in trace.nodes if node.node_id == node_id), None)
            if node:
                return {
                    "node_id": node.node_id,
                    "label": node.content,
                    "type": node.node_type,
                    "confidence": node.confidence,
                    "kg_references": node.kg_references,
                    "metadata": node.metadata,
                }
        for report in self._reports.values():
            if node_id == f"answer:{report.answer_id}":
                return {
                    "node_id": node_id,
                    "label": f"Answer {report.answer_id}",
                    "type": "answer",
                    "confidence": report.overall_confidence,
                    "metadata": {
                        "total_facts": report.total_facts,
                        "verified": report.verified_count,
                        "partial": report.partial_count,
                        "unverified": report.unverified_count,
                        "contradicted": report.contradicted_count,
                    },
                }
            fact_context = self._fact_context(report, node_id)
            if fact_context:
                return fact_context
        return None

    def _fact_context(self, report: VerificationReport, node_id: str) -> dict[str, Any] | None:
        if node_id.startswith("fact:"):
            fact_id = node_id.split(":", 1)[1]
            for result in report.results:
                if result.fact.fact_id == fact_id:
                    return {
                        "node_id": node_id,
                        "label": result.fact.content,
                        "type": "fact",
                        "confidence": result.confidence,
                        "metadata": {
                            "status": result.status.value,
                            "fact_id": result.fact.fact_id,
                            "fact_type": result.fact.fact_type.value,
                            "subject": result.fact.subject,
                            "predicate": result.fact.predicate,
                            "object": result.fact.object,
                        },
                    }
        if node_id.startswith("evidence:"):
            parts = node_id.split(":")
            if len(parts) == 3:
                fact_id = parts[1]
                try:
                    index = int(parts[2]) - 1
                except ValueError:
                    index = -1
                result = next((res for res in report.results if res.fact.fact_id == fact_id), None)
                if result and 0 <= index < len(result.evidences):
                    evidence = result.evidences[index]
                    return {
                        "node_id": node_id,
                        "label": evidence.content,
                        "type": "evidence",
                        "confidence": evidence.confidence,
                        "metadata": {
                            "source_id": evidence.source_id,
                            "source_type": evidence.source_type,
                        },
                    }
        if node_id.startswith("conflict:"):
            parts = node_id.split(":")
            if len(parts) == 3:
                fact_id = parts[1]
                try:
                    index = int(parts[2]) - 1
                except ValueError:
                    index = -1
                result = next((res for res in report.results if res.fact.fact_id == fact_id), None)
                if result and 0 <= index < len(result.conflicts):
                    conflict = result.conflicts[index]
                    return {
                        "node_id": node_id,
                        "label": conflict.content,
                        "type": "conflict",
                        "confidence": conflict.confidence,
                        "metadata": {
                            "source_id": conflict.source_id,
                            "source_type": conflict.source_type,
                        },
                    }
        return None


class VisualizationExportRequest(BaseModel):
    """Payload accepted by the export endpoint."""

    graph: dict[str, Any] = Field(..., description="Graph payload produced by the generator")
    format: Literal["json", "svg", "markdown"] = Field("json", description="Desired export format")
    metadata: dict[str, Any] = Field(default_factory=dict)


_visualization_store = VisualizationMemoryStore()
_data_generator = VisualizationDataGenerator()


def get_visualization_store() -> VisualizationMemoryStore:
    """Dependency hook returning the shared visualization store."""

    return _visualization_store


def get_visualization_generator() -> VisualizationDataGenerator:
    """Dependency hook returning the shared data generator."""

    return _data_generator


@router.get("/trace/{trace_id}")
async def get_trace_visualization(
    trace_id: str,
    store: VisualizationMemoryStore = Depends(get_visualization_store),
    generator: VisualizationDataGenerator = Depends(get_visualization_generator),
) -> dict[str, Any]:
    """Return visualization data derived from a reasoning trace."""

    trace = await store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    graph = generator.from_trace(trace)
    return generator.to_d3_json(graph)


@router.get("/verification/{answer_id}")
async def get_verification_visualization(
    answer_id: str,
    store: VisualizationMemoryStore = Depends(get_visualization_store),
    generator: VisualizationDataGenerator = Depends(get_visualization_generator),
) -> dict[str, Any]:
    """Return visualization data for a verification report."""

    report = await store.get_report(answer_id)
    if not report:
        raise HTTPException(status_code=404, detail="Verification report not found")
    graph = generator.from_verification(report)
    return generator.to_d3_json(graph)


@router.get("/evidence/{node_id}")
async def get_node_evidence(
    node_id: str,
    store: VisualizationMemoryStore = Depends(get_visualization_store),
) -> dict[str, Any]:
    """Return metadata for a visualization node."""

    context = await store.get_node_context(node_id)
    if not context:
        raise HTTPException(status_code=404, detail="Node not found")
    return context


def _graph_to_svg(graph: dict[str, Any]) -> str:
    stats = graph.get("stats") or {}
    nodes = stats.get("nodes", len(graph.get("nodes", [])))
    edges = stats.get("edges", len(graph.get("links", [])))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200">'
        f"<text x='20' y='40'>Nodes: {nodes}</text>"
        f"<text x='20' y='80'>Edges: {edges}</text>"
        "</svg>"
    )


def _graph_to_markdown(graph: dict[str, Any], metadata: dict[str, Any]) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("links", [])
    lines = [
        "# Visualization Export",
        "",
        f"- Nodes: {len(nodes)}",
        f"- Edges: {len(edges)}",
    ]
    if metadata:
        lines.append("- Metadata: ")
        for key, value in metadata.items():
            lines.append(f"  - {key}: {value}")
    if nodes:
        lines.append("\n## Sample Nodes")
        for node in nodes[:3]:
            lines.append(f"- {node.get('label', node.get('id'))} ({node.get('type', 'node')})")
    return "\n".join(lines)


@router.post("/export")
async def export_visualization(
    payload: VisualizationExportRequest = Body(...),
) -> dict[str, Any]:
    """Export graph data in the requested format."""

    fmt = payload.format.lower()
    graph = payload.graph
    if fmt == "json":
        return {"format": "json", "content": graph}
    if fmt == "svg":
        return {"format": "svg", "content": _graph_to_svg(graph)}
    if fmt == "markdown":
        return {
            "format": "markdown",
            "content": _graph_to_markdown(graph, payload.metadata),
        }
    raise HTTPException(status_code=400, detail="Unsupported export format")


__all__ = [
    "router",
    "VisualizationMemoryStore",
    "get_visualization_store",
    "get_visualization_generator",
]
