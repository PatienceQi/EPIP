"""High coverage integration tests for FastAPI endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from epip.api.dependencies import (
    get_query_cache,
)
from epip.api.visualization import (
    VisualizationMemoryStore,
    get_visualization_generator,
    get_visualization_store,
)
from epip.cache import CacheConfig, QueryCache
from epip.verification.fact_extractor import ExtractedFact, FactType
from epip.verification.fact_verifier import Evidence, VerificationResult, VerificationStatus
from epip.verification.report import VerificationReport
from epip.verification.trace import ReasoningTrace, TraceEdge, TraceNode
from epip.visualization import VisualizationDataGenerator


def _build_trace() -> ReasoningTrace:
    now = datetime(2024, 5, 18, tzinfo=timezone.utc)
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


@pytest.fixture()
def visualization_client(api_client: TestClient):
    store = VisualizationMemoryStore()
    generator = VisualizationDataGenerator()
    app = api_client.app
    app.dependency_overrides[get_visualization_store] = lambda: store
    app.dependency_overrides[get_visualization_generator] = lambda: generator
    try:
        yield api_client, store
    finally:
        app.dependency_overrides.pop(get_visualization_store, None)
        app.dependency_overrides.pop(get_visualization_generator, None)


def test_query_endpoint_full_flow(api_client: TestClient) -> None:
    payload = {"query": "Summarize policy", "source": "integration-test"}

    response = api_client.post("/api/query", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "mocked pipeline result"
    assert body["metadata"]["plan"]

    overrides = api_client.app.state.test_overrides
    overrides["query_parser"].parse.assert_awaited_once()
    overrides["entity_linker"].link.assert_awaited_once()
    overrides["query_planner"].plan.assert_awaited_once()
    overrides["query_planner"].to_json.assert_called_once()


def test_visualization_endpoints(visualization_client) -> None:
    client, store = visualization_client
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
        json={"graph": report_payload, "format": "svg"},
    )
    assert export_resp.status_code == 200
    assert export_resp.json()["format"] == "svg"


@pytest.mark.asyncio
async def test_cache_workflow(api_client: TestClient) -> None:
    cache = QueryCache(CacheConfig(redis_url="redis://localhost:0/0", key_prefix="epip:test:"))
    app = api_client.app
    app.dependency_overrides[get_query_cache] = lambda: cache
    app.state.test_overrides["cache"] = cache

    assert await cache.get("demo") is None
    await cache.set("demo", {"value": 1})
    assert await cache.get("demo") == {"value": 1}
    await cache.set("other", {"value": 2})

    stats_resp = api_client.get("/api/cache/stats")
    assert stats_resp.status_code == 200
    stats_payload = stats_resp.json()
    assert stats_payload["hits"] >= 1
    assert stats_payload["misses"] >= 1

    clear_resp = api_client.post("/api/cache/clear", json={"pattern": "demo"})
    assert clear_resp.status_code == 200
    assert clear_resp.json()["cleared"] >= 1
    assert await cache.get("demo") is None
    assert await cache.get("other") == {"value": 2}


def test_error_handling(api_client: TestClient) -> None:
    # Test that unsupported export format returns 422 (Pydantic validation error)
    export_resp = api_client.post(
        "/api/visualization/export",
        json={"graph": {}, "format": "pdf"},
    )
    assert export_resp.status_code == 422  # Pydantic rejects invalid format


def test_query_engine_error_propagation(api_client: TestClient) -> None:
    """Verify that pipeline errors propagate correctly."""
    overrides = api_client.app.state.test_overrides
    engine = overrides["query_engine"]
    engine.query.side_effect = RuntimeError("Pipeline failure")
    try:
        with pytest.raises(RuntimeError, match="Pipeline failure"):
            api_client.post("/api/query", json={"query": "fail", "source": "tests"})
    finally:
        engine.query.side_effect = None
        engine.query.return_value = "mocked pipeline result"
