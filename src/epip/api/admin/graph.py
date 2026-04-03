"""Admin-only Graph management API endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from epip.admin import TenantContext
from epip.api.dependencies import get_neo4j_client
from epip.api.schemas.graph import (
    CreateNodeRequest,
    CreateRelationshipRequest,
    ExportRequest,
    GraphNodeResponse,
    GraphRelationshipResponse,
    ImportNodesRequest,
    ImportRelationshipsRequest,
    ImportResponse,
    MaintenanceResponse,
    UpdateNodeRequest,
)
from epip.db import Neo4jClient

router = APIRouter(prefix="/api/admin/graph", tags=["admin-graph"])


def _require_admin() -> None:
    """Require admin access for the current request."""
    tenant = TenantContext.get_current()
    if tenant is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if tenant.config.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _node_to_response(node: Any) -> GraphNodeResponse:
    """Convert a GraphNode to response model."""
    return GraphNodeResponse(
        id=node.id,
        labels=node.labels,
        properties=node.properties,
    )


def _relationship_to_response(rel: Any) -> GraphRelationshipResponse:
    """Convert a GraphRelationship to response model."""
    return GraphRelationshipResponse(
        id=rel.id,
        type=rel.type,
        start_node_id=rel.start_node_id,
        end_node_id=rel.end_node_id,
        properties=rel.properties,
    )


@router.post("/nodes", response_model=GraphNodeResponse)
async def create_node(
    request: CreateNodeRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> GraphNodeResponse:
    """Create a new node (admin only)."""
    _require_admin()
    node = await neo4j.create_node(labels=request.labels, properties=request.properties)
    return _node_to_response(node)


@router.put("/nodes/{node_id}", response_model=GraphNodeResponse)
async def update_node(
    node_id: str,
    request: UpdateNodeRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> GraphNodeResponse:
    """Update a node's properties (admin only)."""
    _require_admin()
    node = await neo4j.update_node(node_id, properties=request.properties)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return _node_to_response(node)


@router.delete("/nodes/{node_id}")
async def delete_node(
    node_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> dict[str, bool]:
    """Delete a node and its relationships (admin only)."""
    _require_admin()
    deleted = await neo4j.delete_node(node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"deleted": True}


@router.post("/relationships", response_model=GraphRelationshipResponse)
async def create_relationship(
    request: CreateRelationshipRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> GraphRelationshipResponse:
    """Create a relationship between two nodes (admin only)."""
    _require_admin()
    try:
        rel = await neo4j.create_relationship(
            start_node_id=request.start_node_id,
            end_node_id=request.end_node_id,
            rel_type=request.type,
            properties=request.properties,
        )
        return _relationship_to_response(rel)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create relationship: {str(e)}")


@router.delete("/relationships/{rel_id}")
async def delete_relationship(
    rel_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> dict[str, bool]:
    """Delete a relationship (admin only)."""
    _require_admin()
    deleted = await neo4j.delete_relationship(rel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {"deleted": True}


@router.post("/import/nodes", response_model=ImportResponse)
async def import_nodes(
    request: ImportNodesRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> ImportResponse:
    """Bulk import nodes (admin only)."""
    _require_admin()
    created = 0
    failed = 0
    errors: list[str] = []

    for i, node_req in enumerate(request.nodes):
        try:
            await neo4j.create_node(labels=node_req.labels, properties=node_req.properties)
            created += 1
        except Exception as e:
            failed += 1
            errors.append(f"Node {i}: {str(e)}")

    return ImportResponse(created=created, failed=failed, errors=errors[:10])


@router.post("/import/relationships", response_model=ImportResponse)
async def import_relationships(
    request: ImportRelationshipsRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> ImportResponse:
    """Bulk import relationships (admin only)."""
    _require_admin()
    created = 0
    failed = 0
    errors: list[str] = []

    for i, rel_req in enumerate(request.relationships):
        try:
            await neo4j.create_relationship(
                start_node_id=rel_req.start_node_id,
                end_node_id=rel_req.end_node_id,
                rel_type=rel_req.type,
                properties=rel_req.properties,
            )
            created += 1
        except Exception as e:
            failed += 1
            errors.append(f"Relationship {i}: {str(e)}")

    return ImportResponse(created=created, failed=failed, errors=errors[:10])


@router.post("/import/file", response_model=ImportResponse)
async def import_from_file(
    file: UploadFile = File(...),
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> ImportResponse:
    """Import nodes and relationships from a JSON file (admin only)."""
    _require_admin()

    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON files are supported")

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    created = 0
    failed = 0
    errors: list[str] = []
    node_id_map: dict[str, str] = {}  # Map old IDs to new IDs

    # Import nodes first
    for i, node_data in enumerate(data.get("nodes", [])):
        try:
            labels = node_data.get("labels", ["Node"])
            properties = node_data.get("properties", {})
            old_id = node_data.get("id", str(i))

            node = await neo4j.create_node(labels=labels, properties=properties)
            node_id_map[old_id] = node.id
            created += 1
        except Exception as e:
            failed += 1
            errors.append(f"Node {i}: {str(e)}")

    # Import relationships
    for i, rel_data in enumerate(data.get("relationships", [])):
        try:
            start_id = node_id_map.get(rel_data.get("start_node_id", ""))
            end_id = node_id_map.get(rel_data.get("end_node_id", ""))

            if not start_id or not end_id:
                failed += 1
                errors.append(f"Relationship {i}: Invalid node reference")
                continue

            await neo4j.create_relationship(
                start_node_id=start_id,
                end_node_id=end_id,
                rel_type=rel_data.get("type", "RELATED_TO"),
                properties=rel_data.get("properties", {}),
            )
            created += 1
        except Exception as e:
            failed += 1
            errors.append(f"Relationship {i}: {str(e)}")

    return ImportResponse(created=created, failed=failed, errors=errors[:10])


@router.post("/export")
async def export_graph(
    request: ExportRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> JSONResponse:
    """Export graph data as JSON (admin only)."""
    _require_admin()

    nodes = await neo4j.get_nodes(label=request.label, limit=request.limit)

    relationships = []
    if request.include_relationships:
        for node in nodes:
            node_rels = await neo4j.get_node_relationships(node.id)
            relationships.extend(node_rels)

    # Remove duplicates from relationships
    seen_rel_ids: set[str] = set()
    unique_relationships = []
    for rel in relationships:
        if rel.id not in seen_rel_ids:
            seen_rel_ids.add(rel.id)
            unique_relationships.append(rel)

    export_data = {
        "nodes": [{"id": n.id, "labels": n.labels, "properties": n.properties} for n in nodes],
        "relationships": [
            {
                "id": r.id,
                "type": r.type,
                "start_node_id": r.start_node_id,
                "end_node_id": r.end_node_id,
                "properties": r.properties,
            }
            for r in unique_relationships
        ],
    }

    return JSONResponse(
        content=export_data,
        headers={"Content-Disposition": f"attachment; filename=graph_export.{request.format}"},
    )


@router.post("/maintenance/reindex", response_model=MaintenanceResponse)
async def reindex_database(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> MaintenanceResponse:
    """Recreate database indexes (admin only)."""
    _require_admin()

    try:
        # Get all labels and create indexes for common properties
        labels = await neo4j.get_labels()
        index_count = 0

        for label in labels:
            try:
                # Create index on 'name' property if it exists
                await neo4j.execute_write(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.name)")
                index_count += 1
            except Exception:
                pass  # Index might already exist or property doesn't exist

        return MaintenanceResponse(
            operation="reindex",
            success=True,
            affected_count=index_count,
            message=f"Created/verified indexes for {len(labels)} labels",
        )
    except Exception as e:
        return MaintenanceResponse(
            operation="reindex",
            success=False,
            message=str(e),
        )


@router.delete("/maintenance/orphans", response_model=MaintenanceResponse)
async def delete_orphan_nodes(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> MaintenanceResponse:
    """Delete nodes with no relationships (admin only)."""
    _require_admin()

    try:
        result = await neo4j.execute_write(
            """
            MATCH (n)
            WHERE NOT (n)--()
            WITH n LIMIT 1000
            DELETE n
            RETURN count(n) as deleted
            """
        )
        deleted = result[0].get("deleted", 0) if result else 0

        return MaintenanceResponse(
            operation="delete_orphans",
            success=True,
            affected_count=deleted,
            message=f"Deleted {deleted} orphan nodes",
        )
    except Exception as e:
        return MaintenanceResponse(
            operation="delete_orphans",
            success=False,
            message=str(e),
        )


@router.get("/health")
async def graph_health(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> dict[str, Any]:
    """Get Neo4j health status (admin only)."""
    _require_admin()

    is_healthy = await neo4j.ping()
    stats = await neo4j.get_stats() if is_healthy else None

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "connected": is_healthy,
        "stats": {
            "node_count": stats.node_count if stats else 0,
            "relationship_count": stats.relationship_count if stats else 0,
        }
        if stats
        else None,
    }


__all__ = ["router"]
