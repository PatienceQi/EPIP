"""Tests for reasoning trace utilities."""

from __future__ import annotations

import pytest

from epip.verification.path_analyzer import PathAnalyzer
from epip.verification.provenance import ProvenanceService
from epip.verification.trace import TraceRecorder


class StubKG:
    """Minimal KG client used in provenance tests."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_node(self, node_id: str) -> dict[str, str]:
        self.calls.append(node_id)
        return {"id": node_id, "label": f"Node {node_id}"}


def test_trace_recorder_record_node_populates_fields():
    recorder = TraceRecorder()

    node_id = recorder.record_node(
        node_type="thought",
        content="Collect vaccination data",
        confidence=0.75,
        kg_refs=["kg-1", "kg-1", "kg-2"],
    )
    trace = recorder.build_trace("How reliable is the report?")

    assert node_id == "node-1"
    assert trace.total_steps == 1
    node = trace.nodes[0]
    assert node.node_type == "thought"
    assert node.content == "Collect vaccination data"
    assert node.confidence == pytest.approx(0.75)
    assert node.kg_references == ["kg-1", "kg-2"]
    assert trace.critical_path == ["node-1"]


def test_trace_recorder_find_critical_path_prefers_high_scoring_path():
    recorder = TraceRecorder()
    first = recorder.record_node("thought", "Plan analysis", 0.5, ["kg-a"])
    evidence = recorder.record_node("observation", "Admissions increased", 0.8, ["kg-b"])
    detour = recorder.record_node("action", "Run auxiliary job", 0.4, ["kg-c"])
    conclusion = recorder.record_node("conclusion", "Admissions tied to policy", 0.9, ["kg-d"])

    recorder.record_edge(first, evidence, "supports", 0.3)
    recorder.record_edge(evidence, conclusion, "leads_to", 0.4)
    recorder.record_edge(first, detour, "leads_to", 0.5)
    recorder.record_edge(detour, conclusion, "supports", 0.1)

    path = recorder.find_critical_path()

    assert path == [first, evidence, conclusion]


def test_path_analyzer_find_weak_points_filters_low_confidence_nodes():
    recorder = TraceRecorder()
    strong = recorder.record_node("thought", "Start", 0.9, [])
    weak = recorder.record_node("observation", "Unverified data point", 0.45, [])
    recorder.record_edge(strong, weak, "supports", 0.3)
    trace = recorder.build_trace("trace confidence")

    analyzer = PathAnalyzer()
    weak_nodes = analyzer.find_weak_points(trace, threshold=0.6)

    assert weak_nodes == [weak]


@pytest.mark.asyncio
async def test_provenance_service_trace_back_returns_sources():
    recorder = TraceRecorder()
    source = recorder.record_node("observation", "Hospital reports", 0.6, ["kg:source"])
    bridge = recorder.record_node("thought", "Interpret reports", 0.5, [])
    conclusion = recorder.record_node("conclusion", "Admissions stable", 0.8, ["kg:conclusion"])
    recorder.record_edge(source, bridge, "supports", 0.4)
    recorder.record_edge(bridge, conclusion, "leads_to", 0.9)
    trace = recorder.build_trace("Are admissions stable?")

    service = ProvenanceService(kg_client=StubKG())
    info = await service.trace_back(conclusion, trace)

    assert info.conclusion == "Admissions stable"
    assert info.source_nodes == [source, bridge]
    assert info.reasoning_chain == [source, bridge, conclusion]
    assert info.evidence_count == 1
    assert info.confidence == pytest.approx((0.6 + 0.5 + 0.8) / 3)


def test_provenance_service_build_reasoning_chain_prefers_strong_edges():
    recorder = TraceRecorder()
    root = recorder.record_node("thought", "Initial plan", 0.7, [])
    helper = recorder.record_node("action", "Gather new stats", 0.65, [])
    conclusion = recorder.record_node("conclusion", "Final summary", 0.9, [])
    recorder.record_edge(root, conclusion, "supports", 0.2)
    recorder.record_edge(root, helper, "supports", 0.6)
    recorder.record_edge(helper, conclusion, "leads_to", 0.8)
    trace = recorder.build_trace("Explain decision")

    service = ProvenanceService(None)
    chain = service.build_reasoning_chain(trace, conclusion)

    assert chain == [root, helper, conclusion]
