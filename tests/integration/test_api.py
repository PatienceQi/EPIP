"""Integration tests covering FastAPI routes."""

from fastapi.testclient import TestClient


def test_status_endpoint_returns_environment(api_client: TestClient) -> None:
    response = api_client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "development"
    assert "version" in body


def test_query_endpoint_runs_pipeline(api_client: TestClient) -> None:
    payload = {"query": "Summarize policy", "source": "tests"}

    response = api_client.post("/api/query", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "mocked pipeline result"
    metadata = body["metadata"]
    assert metadata["source"] == "tests"
    assert metadata["intent"] == "fact"
    assert metadata["plan"]

    overrides = api_client.app.state.test_overrides
    mock_engine = overrides["query_engine"]
    mock_engine.query.assert_awaited_once()
    assert mock_engine.query.await_args.args == ("Summarize policy",)


def test_cache_stats_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/api/cache/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["hits"] == 1
    assert body["misses"] == 1
    overrides = api_client.app.state.test_overrides
    overrides["cache"].stats.assert_awaited_once()


def test_cache_clear_endpoint(api_client: TestClient) -> None:
    payload = {"pattern": "demo*"}

    response = api_client.post("/api/cache/clear", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["cleared"] == 2
    assert body["pattern"] == "demo*"
    overrides = api_client.app.state.test_overrides
    overrides["cache"].clear.assert_awaited_once_with("demo*")
