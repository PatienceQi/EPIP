"""Graph browsing API endpoints."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from epip.admin import TenantContext
from epip.api.dependencies import get_neo4j_client
from epip.api.schemas.graph import (
    CypherExecuteRequest,
    CypherExecuteResponse,
    ExpandNodeRequest,
    GraphDataResponse,
    GraphNodeResponse,
    GraphRelationshipResponse,
    GraphStatsResponse,
    LinkPredictionRequest,
    LinkPredictionResponse,
    NodesListResponse,
    PredictedLinkResponse,
    SearchNodesRequest,
)
from epip.db import Neo4jClient

router = APIRouter(prefix="/api/graph", tags=["graph"])

WRITE_KEYWORDS = frozenset({"CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP", "DETACH"})


def _is_write_query(cypher: str) -> bool:
    """Check if a Cypher query contains write operations."""
    tokens = cypher.upper().split()
    return any(keyword in tokens for keyword in WRITE_KEYWORDS)


def _is_admin() -> bool:
    """Check if the current tenant is an admin."""
    tenant = TenantContext.get_current()
    if tenant is None:
        return False
    return tenant.config.get("role") == "admin"


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


@router.get("/nodes", response_model=NodesListResponse)
async def list_nodes(
    label: str | None = Query(default=None, description="Filter by label"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum nodes to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> NodesListResponse:
    """List nodes with optional filtering and pagination."""
    nodes = await neo4j.get_nodes(label=label, limit=limit, offset=offset)
    return NodesListResponse(
        nodes=[_node_to_response(n) for n in nodes],
        total=-1,  # Total count not available without additional query
        limit=limit,
        offset=offset,
    )


@router.get("/nodes/{node_id}", response_model=GraphNodeResponse)
async def get_node(
    node_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> GraphNodeResponse:
    """Get a single node by ID."""
    node = await neo4j.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return _node_to_response(node)


@router.get("/nodes/{node_id}/relationships", response_model=list[GraphRelationshipResponse])
async def get_node_relationships(
    node_id: str,
    direction: str = Query(default="both", regex="^(both|incoming|outgoing)$"),
    rel_type: str | None = Query(default=None, description="Filter by relationship type"),
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> list[GraphRelationshipResponse]:
    """Get relationships for a node."""
    relationships = await neo4j.get_node_relationships(
        node_id, direction=direction, rel_type=rel_type
    )
    return [_relationship_to_response(r) for r in relationships]


@router.post("/nodes/{node_id}/expand", response_model=GraphDataResponse)
async def expand_node(
    node_id: str,
    request: ExpandNodeRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> GraphDataResponse:
    """Expand a node to get its neighbors."""
    nodes, relationships = await neo4j.expand_node(node_id, depth=request.depth)
    return GraphDataResponse(
        nodes=[_node_to_response(n) for n in nodes],
        relationships=[_relationship_to_response(r) for r in relationships],
    )


@router.get("/labels", response_model=list[str])
async def list_labels(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> list[str]:
    """Get all node labels in the database."""
    return await neo4j.get_labels()


@router.get("/relationship-types", response_model=list[str])
async def list_relationship_types(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> list[str]:
    """Get all relationship types in the database."""
    return await neo4j.get_relationship_types()


@router.post("/search", response_model=list[GraphNodeResponse])
async def search_nodes(
    request: SearchNodesRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> list[GraphNodeResponse]:
    """Search nodes by property values."""
    nodes = await neo4j.search_nodes(
        query_text=request.query,
        label=request.label,
        limit=request.limit,
    )
    return [_node_to_response(n) for n in nodes]


@router.get("/stats", response_model=GraphStatsResponse)
async def get_stats(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> GraphStatsResponse:
    """Get graph statistics."""
    stats = await neo4j.get_stats()
    return GraphStatsResponse(
        node_count=stats.node_count,
        relationship_count=stats.relationship_count,
        label_counts=stats.label_counts,
        relationship_type_counts=stats.relationship_type_counts,
    )


@router.post("/cypher", response_model=CypherExecuteResponse)
async def execute_cypher(
    request: CypherExecuteRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> CypherExecuteResponse:
    """Execute a Cypher query.

    Non-admin users can only execute read queries.
    """
    is_write = _is_write_query(request.query)

    if is_write and not _is_admin():
        raise HTTPException(
            status_code=403,
            detail="Write operations require admin access",
        )

    start_time = time.time()
    try:
        if is_write:
            result = await neo4j.execute_write(request.query, request.parameters)
        else:
            result = await neo4j.execute_read(request.query, request.parameters)

        execution_time = (time.time() - start_time) * 1000

        columns = list(result[0].keys()) if result else []

        return CypherExecuteResponse(
            success=True,
            data=result,
            columns=columns,
            execution_time_ms=execution_time,
            is_write_query=is_write,
        )
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        raise HTTPException(
            status_code=400,
            detail=f"Query execution failed: {str(e)}",
        )


@router.post("/algorithms/link-prediction", response_model=LinkPredictionResponse)
async def predict_links(
    request: LinkPredictionRequest,
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> LinkPredictionResponse:
    """Predict potential links for a node using graph algorithms."""
    # Get the source node to verify it exists
    source_node = await neo4j.get_node(request.node_id)
    if source_node is None:
        raise HTTPException(status_code=404, detail="Source node not found")

    # Run link prediction based on algorithm
    if request.algorithm == "common_neighbors":
        query = """
            MATCH (n)-[:RELATED_TO]-(neighbor)-[:RELATED_TO]-(candidate)
            WHERE elementId(n) = $node_id AND NOT (n)-[:RELATED_TO]-(candidate) AND n <> candidate
            WITH candidate, count(DISTINCT neighbor) as score
            ORDER BY score DESC
            LIMIT $limit
            RETURN elementId(candidate) as id, labels(candidate) as labels,
                   properties(candidate) as properties, score
        """
    elif request.algorithm == "adamic_adar":
        query = """
            MATCH (n)-[:RELATED_TO]-(neighbor)-[:RELATED_TO]-(candidate)
            WHERE elementId(n) = $node_id AND NOT (n)-[:RELATED_TO]-(candidate) AND n <> candidate
            WITH candidate, neighbor
            MATCH (neighbor)-[:RELATED_TO]-(other)
            WITH candidate, neighbor, count(other) as degree
            WITH candidate, sum(1.0 / log(degree + 1)) as score
            ORDER BY score DESC
            LIMIT $limit
            RETURN elementId(candidate) as id, labels(candidate) as labels,
                   properties(candidate) as properties, score
        """
    else:  # preferential_attachment
        query = """
            MATCH (n)-[:RELATED_TO]-(neighbor)-[:RELATED_TO]-(candidate)
            WHERE elementId(n) = $node_id AND NOT (n)-[:RELATED_TO]-(candidate) AND n <> candidate
            WITH n, candidate
            MATCH (n)-[:RELATED_TO]-(n_neighbor)
            WITH candidate, count(DISTINCT n_neighbor) as n_degree
            MATCH (candidate)-[:RELATED_TO]-(c_neighbor)
            WITH candidate, n_degree * count(DISTINCT c_neighbor) as score
            ORDER BY score DESC
            LIMIT $limit
            RETURN elementId(candidate) as id, labels(candidate) as labels,
                   properties(candidate) as properties, score
        """

    try:
        result = await neo4j.execute_read(
            query,
            {"node_id": request.node_id, "limit": request.limit},
        )
    except Exception:
        # Fallback to simpler query if the above fails (e.g., no RELATED_TO edges)
        result = []

    predictions = [
        PredictedLinkResponse(
            target_node=GraphNodeResponse(
                id=r["id"],
                labels=r["labels"],
                properties=r["properties"],
            ),
            score=float(r.get("score", 0)),
            algorithm=request.algorithm,
        )
        for r in result
    ]

    return LinkPredictionResponse(
        source_node_id=request.node_id,
        predictions=predictions,
    )


__all__ = ["router"]
