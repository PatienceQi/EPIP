"""Tests for visualization data generator and API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from epip.api.visualization import (
    VisualizationMemoryStore,
    get_visualization_generator,
    get_visualization_store,
)
from epip.verification.fact_extractor import ExtractedFact, FactType
from epip.verification.fact_verifier import Evidence, VerificationResult, VerificationStatus
from epip.verification.report import VerificationReport
from epip.verification.trace import ReasoningTrace, TraceEdge, TraceNode
from epip.visualization import VisEdge, VisGraph, VisNode, VisualizationDataGenerator


def _build_trace() -> ReasoningTrace:
    now = datetime(2024, 5, 18, tzinfo=UTC)
    nodes = [
        TraceNode(
            node_id="node-1",
            node_type="thought",
            content="Formulate approach",
            confidence=0.9,
            timestamp=now,
            kg_references=["kg:1"],
            metadata={"role": "planner"},
        ),
        TraceNode(
            node_id="node-2",
            node_type="observation",
            content="Review hospital stats",
            confidence=0.6,
            timestamp=now,
            kg_references=["kg:2"],
            metadata={},
        ),
    ]
    edges = [
        TraceEdge(
            source_id="node-1",
            target_id="node-2",
            edge_type="supports",
            weight=0.4,
        )
    ]
    return ReasoningTrace(
        trace_id="trace-demo",
        query="Explain readiness",
        nodes=nodes,
        edges=edges,
        critical_path=["node-1", "node-2"],
        total_steps=len(nodes),
        avg_confidence=sum(node.confidence for node in nodes) / len(nodes),
    )


def _build_report() -> VerificationReport:
    fact = ExtractedFact(
        fact_id="fact-1",
        content="Policy updated in 2024",
        fact_type=FactType.RELATION,
        subject="Policy",
        predicate="updated",
        object="2024",
        source_span=(0, 10),
    )
    evidence = Evidence(
        source_type="document",
        source_id="doc-7",
        content="Government memo 2024 update",
        confidence=0.8,
    )
    result = VerificationResult(
        fact=fact,
        status=VerificationStatus.VERIFIED,
        confidence=0.85,
        evidences=[evidence],
        conflicts=[],
        explanation="Supported by memo",
    )
    return VerificationReport(
        answer_id="answer-1",
        total_facts=1,
        verified_count=1,
        partial_count=0,
        unverified_count=0,
        contradicted_count=0,
        overall_confidence=0.88,
        results=[result],
        filtered_facts=[],
    )


def test_visualization_generator_from_trace_highlights_nodes():
    generator = VisualizationDataGenerator()
    trace = _build_trace()

    graph = generator.from_trace(trace)

    assert len(graph.nodes) == 2
    node_map = {node.id: node for node in graph.nodes}
    assert node_map["node-1"].metadata["critical"] is True
    assert node_map["node-2"].metadata["critical"] is True
    assert graph.edges[0].label == "supports"
    assert graph.edges[0].source == "node-1"


def test_visualization_confidence_to_color_gradient_boundaries():
    generator = VisualizationDataGenerator()

    assert generator._confidence_to_color(0.0) == "#d61c2b"
    assert generator._confidence_to_color(0.5) == "#f2c037"
    assert generator._confidence_to_color(1.0) == "#19a974"


def test_visualization_to_d3_json_reports_stats():
    generator = VisualizationDataGenerator()
    graph = VisGraph(
        nodes=[
            VisNode(
                id="a",
                label="Node A",
                type="thought",
                confidence=0.7,
                color="#ffffff",
                size=20,
                metadata={},
            )
        ],
        edges=[
            VisEdge(
                source="a",
                target="b",
                label="leads_to",
                weight=1.0,
                color="#000000",
            )
        ],
        layout="circular",
    )

    payload = generator.to_d3_json(graph)

    assert payload["layout"] == "circular"
    assert payload["stats"]["nodes"] == 1
    assert payload["stats"]["edges"] == 1
    assert payload["links"][0]["source"] == "a"


@pytest.fixture()
def visualization_test_client(api_client):
    store = VisualizationMemoryStore()
    generator = VisualizationDataGenerator()
    api_client.app.dependency_overrides[get_visualization_store] = lambda: store
    api_client.app.dependency_overrides[get_visualization_generator] = lambda: generator
    try:
        yield api_client, store
    finally:
        api_client.app.dependency_overrides.pop(get_visualization_store, None)
        api_client.app.dependency_overrides.pop(get_visualization_generator, None)


def test_visualization_api_endpoints(visualization_test_client):
    client, store = visualization_test_client
    trace = _build_trace()
    report = _build_report()
    store.set_trace(trace)
    store.set_report(report)

    trace_resp = client.get(f"/api/visualization/trace/{trace.trace_id}")
    assert trace_resp.status_code == 200
    trace_payload = trace_resp.json()
    assert trace_payload["stats"]["nodes"] == 2

    report_resp = client.get(f"/api/visualization/verification/{report.answer_id}")
    assert report_resp.status_code == 200
    report_payload = report_resp.json()
    assert report_payload["stats"]["nodes"] >= 2

    context_resp = client.get("/api/visualization/evidence/fact:fact-1")
    assert context_resp.status_code == 200
    assert context_resp.json()["metadata"]["status"] == "verified"

    export_resp = client.post(
        "/api/visualization/export",
        json={
            "graph": report_payload,
            "format": "markdown",
            "metadata": {"title": "demo"},
        },
    )
    assert export_resp.status_code == 200
    data = export_resp.json()
    assert data["format"] == "markdown"
    assert "Visualization Export" in data["content"]
