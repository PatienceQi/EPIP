"""Integration tests for the graph browsing API."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from epip.db.neo4j_client import GraphNode, GraphRelationship, GraphStats
from tests.conftest import mock_neo4j_client  # noqa: F401


def test_list_nodes_returns_nodes(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    nodes = [
        GraphNode(id="node-1", labels=["Policy"], properties={"name": "Alpha"}),
        GraphNode(id="node-2", labels=["Policy"], properties={"name": "Beta"}),
    ]
    mock_neo4j_client.get_nodes.return_value = nodes

    response = api_client.get("/api/graph/nodes", params={"label": "Policy", "limit": 2, "offset": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["offset"] == 5
    assert body["total"] == -1
    assert [n["id"] for n in body["nodes"]] == ["node-1", "node-2"]
    mock_neo4j_client.get_nodes.assert_awaited_once_with(label="Policy", limit=2, offset=5)


def test_get_node_returns_node(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    node = GraphNode(id="node-1", labels=["Policy"], properties={"name": "Alpha"})
    mock_neo4j_client.get_node.return_value = node

    response = api_client.get("/api/graph/nodes/node-1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "node-1"
    assert body["labels"] == ["Policy"]
    assert body["properties"]["name"] == "Alpha"
    mock_neo4j_client.get_node.assert_awaited_once_with("node-1")


def test_get_node_returns_404_when_missing(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    mock_neo4j_client.get_node.return_value = None

    response = api_client.get("/api/graph/nodes/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Node not found"
    mock_neo4j_client.get_node.assert_awaited_once_with("missing")


def test_get_node_relationships_returns_relationships(
    api_client: TestClient, mock_neo4j_client: MagicMock
) -> None:
    relationships = [
        GraphRelationship(
            id="rel-1",
            type="RELATED_TO",
            start_node_id="node-1",
            end_node_id="node-2",
            properties={"weight": 0.4},
        ),
        GraphRelationship(
            id="rel-2",
            type="RELATED_TO",
            start_node_id="node-1",
            end_node_id="node-3",
            properties={"weight": 0.6},
        ),
    ]
    mock_neo4j_client.get_node_relationships.return_value = relationships

    response = api_client.get(
        "/api/graph/nodes/node-1/relationships",
        params={"direction": "incoming", "rel_type": "RELATED_TO"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["properties"]["weight"] == 0.4
    mock_neo4j_client.get_node_relationships.assert_awaited_once_with(
        "node-1", direction="incoming", rel_type="RELATED_TO"
    )


def test_expand_node_returns_graph_data(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    nodes = [
        GraphNode(id="node-2", labels=["Policy"], properties={"name": "Beta"}),
    ]
    relationships = [
        GraphRelationship(
            id="rel-1",
            type="MENTIONS",
            start_node_id="node-1",
            end_node_id="node-2",
            properties={},
        )
    ]
    mock_neo4j_client.expand_node.return_value = (nodes, relationships)

    response = api_client.post("/api/graph/nodes/node-1/expand", json={"depth": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"][0]["id"] == "node-2"
    assert body["relationships"][0]["type"] == "MENTIONS"
    mock_neo4j_client.expand_node.assert_awaited_once_with("node-1", depth=2)


def test_list_labels_returns_labels(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    mock_neo4j_client.get_labels.return_value = ["Policy", "Entity"]

    response = api_client.get("/api/graph/labels")

    assert response.status_code == 200
    assert response.json() == ["Policy", "Entity"]
    mock_neo4j_client.get_labels.assert_awaited_once()


def test_list_relationship_types_returns_types(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    mock_neo4j_client.get_relationship_types.return_value = ["RELATED_TO", "MENTIONS"]

    response = api_client.get("/api/graph/relationship-types")

    assert response.status_code == 200
    assert response.json() == ["RELATED_TO", "MENTIONS"]
    mock_neo4j_client.get_relationship_types.assert_awaited_once()


def test_search_nodes_returns_matches(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    matches = [
        GraphNode(id="node-1", labels=["Policy"], properties={"name": "Alpha"}),
    ]
    mock_neo4j_client.search_nodes.return_value = matches

    payload = {"query": "Alpha", "label": "Policy", "limit": 5}
    response = api_client.post("/api/graph/search", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["properties"]["name"] == "Alpha"
    mock_neo4j_client.search_nodes.assert_awaited_once_with(
        query_text="Alpha", label="Policy", limit=5
    )


def test_get_stats_returns_counts(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    stats = GraphStats(
        node_count=42,
        relationship_count=12,
        label_counts={"Policy": 30},
        relationship_type_counts={"RELATED_TO": 12},
    )
    mock_neo4j_client.get_stats.return_value = stats

    response = api_client.get("/api/graph/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["node_count"] == 42
    assert body["relationship_count"] == 12
    assert body["label_counts"]["Policy"] == 30
    mock_neo4j_client.get_stats.assert_awaited_once()


def test_execute_cypher_read_query(api_client: TestClient, mock_neo4j_client: MagicMock) -> None:
    query = "MATCH (n) RETURN n LIMIT $limit"
    result = [{"name": "Alpha"}]
    mock_neo4j_client.execute_read.return_value = result

    response = api_client.post("/api/graph/cypher", json={"query": query, "parameters": {"limit": 1}})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["is_write_query"] is False
    assert body["data"] == result
    assert body["columns"] == ["name"]
    assert body["execution_time_ms"] >= 0
    mock_neo4j_client.execute_read.assert_awaited_once()
    args, kwargs = mock_neo4j_client.execute_read.await_args
    assert kwargs == {}
    assert args[0] == query
    assert args[1] == {"limit": 1}
    mock_neo4j_client.execute_write.assert_not_called()


def test_execute_cypher_rejects_write_queries_for_non_admin(
    api_client: TestClient, mock_neo4j_client: MagicMock
) -> None:
    payload = {"query": "CREATE (n:Policy {name: $name}) RETURN n", "parameters": {"name": "Alpha"}}

    response = api_client.post("/api/graph/cypher", json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "Write operations require admin access"
    mock_neo4j_client.execute_write.assert_not_called()


def test_execute_cypher_write_query_runs_for_admin(
    admin_api_client: TestClient, mock_neo4j_client: MagicMock
) -> None:
    payload = {"query": "CREATE (n:Policy {name: $name}) RETURN n", "parameters": {"name": "Alpha"}}
    mock_neo4j_client.execute_write.return_value = [{"name": "Alpha"}]

    response = admin_api_client.post("/api/graph/cypher", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["is_write_query"] is True
    assert body["data"] == [{"name": "Alpha"}]
    mock_neo4j_client.execute_write.assert_awaited_once_with(
        "CREATE (n:Policy {name: $name}) RETURN n", {"name": "Alpha"}
    )


def test_execute_cypher_returns_error_on_failure(
    api_client: TestClient, mock_neo4j_client: MagicMock
) -> None:
    mock_neo4j_client.execute_read.side_effect = RuntimeError("syntax error")

    response = api_client.post("/api/graph/cypher", json={"query": "MATCH (n) RETURN n", "parameters": {}})

    assert response.status_code == 400
    assert "syntax error" in response.json()["detail"]
    mock_neo4j_client.execute_read.assert_awaited_once()


def test_link_prediction_returns_predictions(
    api_client: TestClient, mock_neo4j_client: MagicMock
) -> None:
    mock_neo4j_client.get_node.return_value = GraphNode(
        id="node-1",
        labels=["Policy"],
        properties={"name": "Alpha"},
    )
    mock_neo4j_client.execute_read.return_value = [
        {"id": "node-2", "labels": ["Policy"], "properties": {"name": "Beta"}, "score": 2.5}
    ]

    payload = {"node_id": "node-1", "algorithm": "common_neighbors", "limit": 2}
    response = api_client.post("/api/graph/algorithms/link-prediction", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["source_node_id"] == "node-1"
    assert len(body["predictions"]) == 1
    prediction = body["predictions"][0]
    assert prediction["algorithm"] == "common_neighbors"
    assert prediction["score"] == pytest.approx(2.5)
    assert prediction["target_node"]["id"] == "node-2"

    mock_neo4j_client.get_node.assert_awaited_once_with("node-1")
    args, kwargs = mock_neo4j_client.execute_read.await_args
    assert kwargs == {}
    assert args[1] == {"node_id": "node-1", "limit": 2}


def test_link_prediction_returns_404_if_source_missing(
    api_client: TestClient, mock_neo4j_client: MagicMock
) -> None:
    mock_neo4j_client.get_node.return_value = None

    payload = {"node_id": "missing", "algorithm": "common_neighbors", "limit": 2}
    response = api_client.post("/api/graph/algorithms/link-prediction", json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Source node not found"
    mock_neo4j_client.get_node.assert_awaited_once_with("missing")
    mock_neo4j_client.execute_read.assert_not_called()
