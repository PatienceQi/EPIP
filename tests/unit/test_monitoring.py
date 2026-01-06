"""Tests covering Prometheus metrics instrumentation and health endpoints."""

from __future__ import annotations

import pytest

from epip.monitoring.metrics import CollectorRegistry, MetricsCollector


@pytest.fixture()
def isolated_metrics_collector() -> MetricsCollector:
    """Provide a collector with its own registry so samples don't leak."""
    return MetricsCollector(registry=CollectorRegistry())


def test_metrics_collector_records_samples(isolated_metrics_collector: MetricsCollector) -> None:
    collector = isolated_metrics_collector
    collector.record_request("GET", "/foo", 200, 0.5)
    collector.record_query("tenant", "search")
    collector.update_cache_ratio("tenant", 0.75)
    collector.update_kg_nodes("tenant", 42)

    payload = collector.get_metrics()
    assert "epip_requests_total" in payload
    assert "epip_queries_total" in payload
    assert "epip_cache_hit_ratio" in payload
    assert "epip_kg_nodes_total" in payload


def test_metrics_endpoint_format(api_client) -> None:
    response = api_client.get("/monitoring/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "epip_requests_total" in response.text


def test_liveness_endpoint(api_client) -> None:
    response = api_client.get("/monitoring/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_endpoint(api_client) -> None:
    response = api_client.get("/monitoring/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["neo4j"] == "up"
    assert data["redis"] == "up"
