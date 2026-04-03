# ruff: noqa: F811
"""Integration tests for the admin graph management API."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from epip.db.neo4j_client import GraphNode, GraphRelationship, GraphStats
from tests.conftest import mock_neo4j_client  # noqa: F401,F811


def test_admin_create_node_creates_node(admin_api_client: TestClient, mock_neo4j_client) -> None:
    mock_neo4j_client.create_node = AsyncMock(
        return_value=GraphNode(id="node-1", labels=["Policy"], properties={"name": "Alpha"})
    )
    payload = {"labels": ["Policy"], "properties": {"name": "Alpha"}}

    response = admin_api_client.post(
        "/api/admin/graph/nodes",
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "node-1"
    assert body["labels"] == ["Policy"]
    assert body["properties"]["name"] == "Alpha"
    mock_neo4j_client.create_node.assert_awaited_once_with(
        labels=["Policy"], properties={"name": "Alpha"}
    )


def test_admin_update_node_returns_updated_node(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.update_node = AsyncMock(
        return_value=GraphNode(id="node-1", labels=["Policy"], properties={"status": "updated"})
    )

    response = admin_api_client.put(
        "/api/admin/graph/nodes/node-1",
        json={"properties": {"status": "updated"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["properties"]["status"] == "updated"
    mock_neo4j_client.update_node.assert_awaited_once_with(
        "node-1", properties={"status": "updated"}
    )


def test_admin_update_node_returns_404_when_missing(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.update_node = AsyncMock(return_value=None)

    response = admin_api_client.put(
        "/api/admin/graph/nodes/missing",
        json={"properties": {"status": "missing"}},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Node not found"
    mock_neo4j_client.update_node.assert_awaited_once_with(
        "missing", properties={"status": "missing"}
    )


def test_admin_delete_node_confirms_deletion(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.delete_node = AsyncMock(return_value=True)

    response = admin_api_client.delete(
        "/api/admin/graph/nodes/node-1",
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    mock_neo4j_client.delete_node.assert_awaited_once_with("node-1")


def test_admin_delete_node_returns_404_when_missing(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.delete_node = AsyncMock(return_value=False)

    response = admin_api_client.delete(
        "/api/admin/graph/nodes/missing",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Node not found"
    mock_neo4j_client.delete_node.assert_awaited_once_with("missing")


def test_admin_create_relationship_returns_relationship(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.create_relationship = AsyncMock(
        return_value=GraphRelationship(
            id="rel-1",
            type="RELATED_TO",
            start_node_id="node-1",
            end_node_id="node-2",
            properties={"weight": 0.7},
        )
    )
    payload = {
        "start_node_id": "node-1",
        "end_node_id": "node-2",
        "type": "RELATED_TO",
        "properties": {"weight": 0.7},
    }

    response = admin_api_client.post(
        "/api/admin/graph/relationships",
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "rel-1"
    assert body["type"] == "RELATED_TO"
    assert body["properties"]["weight"] == 0.7
    mock_neo4j_client.create_relationship.assert_awaited_once_with(
        start_node_id="node-1",
        end_node_id="node-2",
        rel_type="RELATED_TO",
        properties={"weight": 0.7},
    )


def test_admin_create_relationship_handles_failure(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.create_relationship = AsyncMock(side_effect=RuntimeError("invalid data"))
    payload = {
        "start_node_id": "node-1",
        "end_node_id": "node-2",
        "type": "RELATED_TO",
        "properties": {"weight": 0.7},
    }

    response = admin_api_client.post(
        "/api/admin/graph/relationships",
        json=payload,
    )

    assert response.status_code == 400
    assert "invalid data" in response.json()["detail"]
    mock_neo4j_client.create_relationship.assert_awaited_once()


def test_admin_delete_relationship_confirms_deletion(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.delete_relationship = AsyncMock(return_value=True)

    response = admin_api_client.delete(
        "/api/admin/graph/relationships/rel-1",
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    mock_neo4j_client.delete_relationship.assert_awaited_once_with("rel-1")


def test_admin_delete_relationship_returns_404_when_missing(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.delete_relationship = AsyncMock(return_value=False)

    response = admin_api_client.delete(
        "/api/admin/graph/relationships/missing",
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Relationship not found"
    mock_neo4j_client.delete_relationship.assert_awaited_once_with("missing")


def test_admin_import_nodes_tracks_failures(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.create_node = AsyncMock(
        side_effect=[
            GraphNode(id="node-1", labels=["Policy"], properties={"name": "Alpha"}),
            RuntimeError("duplicate node"),
        ]
    )
    payload = {
        "nodes": [
            {"labels": ["Policy"], "properties": {"name": "Alpha"}},
            {"labels": ["Policy"], "properties": {"name": "Beta"}},
        ]
    }

    response = admin_api_client.post(
        "/api/admin/graph/import/nodes",
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["failed"] == 1
    assert body["errors"] == ["Node 1: duplicate node"]
    assert mock_neo4j_client.create_node.await_count == 2
    first_call = mock_neo4j_client.create_node.await_args_list[0]
    assert first_call.kwargs == {"labels": ["Policy"], "properties": {"name": "Alpha"}}


def test_admin_import_relationships_tracks_failures(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.create_relationship = AsyncMock(
        side_effect=[
            GraphRelationship(
                id="rel-1",
                type="RELATED_TO",
                start_node_id="node-1",
                end_node_id="node-2",
                properties={},
            ),
            RuntimeError("invalid references"),
        ]
    )
    payload = {
        "relationships": [
            {
                "start_node_id": "node-1",
                "end_node_id": "node-2",
                "type": "RELATED_TO",
                "properties": {},
            },
            {
                "start_node_id": "node-2",
                "end_node_id": "node-3",
                "type": "RELATED_TO",
                "properties": {},
            },
        ]
    }

    response = admin_api_client.post(
        "/api/admin/graph/import/relationships",
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["failed"] == 1
    assert body["errors"] == ["Relationship 1: invalid references"]
    assert mock_neo4j_client.create_relationship.await_count == 2
    call_kwargs = mock_neo4j_client.create_relationship.await_args_list[0].kwargs
    assert call_kwargs["start_node_id"] == "node-1"
    assert call_kwargs["end_node_id"] == "node-2"


def test_admin_reindex_database_returns_summary(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.get_labels = AsyncMock(return_value=["Policy", "Entity"])
    mock_neo4j_client.execute_write = AsyncMock()

    response = admin_api_client.post(
        "/api/admin/graph/maintenance/reindex",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["affected_count"] == 2
    assert mock_neo4j_client.execute_write.await_count == 2
    query = mock_neo4j_client.execute_write.await_args_list[0].args[0]
    assert "Policy" in query


def test_admin_reindex_database_handles_error(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.get_labels = AsyncMock(side_effect=RuntimeError("neo4j offline"))

    response = admin_api_client.post(
        "/api/admin/graph/maintenance/reindex",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "neo4j offline"


def test_admin_delete_orphans_returns_count(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.execute_write = AsyncMock(return_value=[{"deleted": 3}])

    response = admin_api_client.delete(
        "/api/admin/graph/maintenance/orphans",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["affected_count"] == 3
    mock_neo4j_client.execute_write.assert_awaited_once()


def test_admin_delete_orphans_handles_error(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.execute_write = AsyncMock(side_effect=RuntimeError("locked"))

    response = admin_api_client.delete(
        "/api/admin/graph/maintenance/orphans",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "locked"


def test_admin_health_returns_stats_when_healthy(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.ping = AsyncMock(return_value=True)
    mock_neo4j_client.get_stats = AsyncMock(
        return_value=GraphStats(
            node_count=10,
            relationship_count=5,
            label_counts={},
            relationship_type_counts={},
        )
    )

    response = admin_api_client.get(
        "/api/admin/graph/health",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["connected"] is True
    assert body["stats"]["node_count"] == 10
    mock_neo4j_client.get_stats.assert_awaited_once()


def test_admin_health_reports_unhealthy_when_ping_fails(
    admin_api_client: TestClient, mock_neo4j_client
) -> None:
    mock_neo4j_client.ping = AsyncMock(return_value=False)
    mock_neo4j_client.get_stats = AsyncMock()

    response = admin_api_client.get(
        "/api/admin/graph/health",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["connected"] is False
    assert body["stats"] is None
    mock_neo4j_client.get_stats.assert_not_called()


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("post", "/api/admin/graph/nodes", {"labels": ["Policy"], "properties": {}}),
        ("put", "/api/admin/graph/nodes/node-1", {"properties": {}}),
        ("delete", "/api/admin/graph/nodes/node-1", None),
        (
            "post",
            "/api/admin/graph/relationships",
            {"start_node_id": "a", "end_node_id": "b", "type": "RELATES", "properties": {}},
        ),
        ("delete", "/api/admin/graph/relationships/rel-1", None),
        (
            "post",
            "/api/admin/graph/import/nodes",
            {"nodes": [{"labels": ["Policy"], "properties": {}}]},
        ),
        (
            "post",
            "/api/admin/graph/import/relationships",
            {
                "relationships": [
                    {"start_node_id": "a", "end_node_id": "b", "type": "RELATES", "properties": {}}
                ]
            },
        ),
        ("post", "/api/admin/graph/maintenance/reindex", None),
        ("delete", "/api/admin/graph/maintenance/orphans", None),
        ("get", "/api/admin/graph/health", None),
    ],
)
def test_admin_graph_endpoints_require_admin(
    api_client: TestClient,
    mock_neo4j_client,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    kwargs = {"json": payload} if payload is not None else {}
    response = api_client.request(method, path, **kwargs)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"
