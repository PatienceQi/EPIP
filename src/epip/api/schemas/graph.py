"""Pydantic models for Graph API endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GraphNodeResponse(BaseModel):
    """Response model for a graph node."""

    id: str = Field(..., description="Unique node identifier")
    labels: list[str] = Field(default_factory=list, description="Node labels")
    properties: dict[str, Any] = Field(default_factory=dict, description="Node properties")


class GraphRelationshipResponse(BaseModel):
    """Response model for a graph relationship."""

    id: str = Field(..., description="Unique relationship identifier")
    type: str = Field(..., description="Relationship type")
    start_node_id: str = Field(..., description="Source node ID")
    end_node_id: str = Field(..., description="Target node ID")
    properties: dict[str, Any] = Field(default_factory=dict, description="Relationship properties")


class GraphDataResponse(BaseModel):
    """Response model for graph data (nodes and relationships)."""

    nodes: list[GraphNodeResponse] = Field(default_factory=list)
    relationships: list[GraphRelationshipResponse] = Field(default_factory=list)


class GraphStatsResponse(BaseModel):
    """Response model for graph statistics."""

    node_count: int = Field(..., description="Total number of nodes")
    relationship_count: int = Field(..., description="Total number of relationships")
    label_counts: dict[str, int] = Field(default_factory=dict, description="Node count per label")
    relationship_type_counts: dict[str, int] = Field(
        default_factory=dict, description="Relationship count per type"
    )


class NodesListResponse(BaseModel):
    """Paginated response for node list."""

    nodes: list[GraphNodeResponse]
    total: int = Field(..., description="Total count (if available)")
    limit: int
    offset: int


class CreateNodeRequest(BaseModel):
    """Request model for creating a node."""

    labels: list[str] = Field(..., min_length=1, description="Node labels (at least one required)")
    properties: dict[str, Any] = Field(default_factory=dict, description="Node properties")


class UpdateNodeRequest(BaseModel):
    """Request model for updating a node."""

    properties: dict[str, Any] = Field(..., description="Properties to update/add")


class CreateRelationshipRequest(BaseModel):
    """Request model for creating a relationship."""

    start_node_id: str = Field(..., description="Source node ID")
    end_node_id: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Relationship type")
    properties: dict[str, Any] = Field(default_factory=dict, description="Relationship properties")


class CypherExecuteRequest(BaseModel):
    """Request model for executing Cypher queries."""

    query: str = Field(..., min_length=1, description="Cypher query to execute")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Query parameters")


class CypherExecuteResponse(BaseModel):
    """Response model for Cypher query execution."""

    success: bool = Field(..., description="Whether the query executed successfully")
    data: list[dict[str, Any]] = Field(default_factory=list, description="Query results")
    columns: list[str] = Field(default_factory=list, description="Result column names")
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")
    is_write_query: bool = Field(..., description="Whether this was a write operation")


class ExpandNodeRequest(BaseModel):
    """Request model for expanding a node."""

    depth: int = Field(default=1, ge=1, le=3, description="Expansion depth (1-3)")


class SearchNodesRequest(BaseModel):
    """Request model for searching nodes."""

    query: str = Field(..., min_length=1, description="Search query")
    label: str | None = Field(default=None, description="Filter by label")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")


class ImportNodesRequest(BaseModel):
    """Request model for bulk importing nodes."""

    nodes: list[CreateNodeRequest] = Field(..., min_length=1, description="Nodes to import")


class ImportRelationshipsRequest(BaseModel):
    """Request model for bulk importing relationships."""

    relationships: list[CreateRelationshipRequest] = Field(
        ..., min_length=1, description="Relationships to import"
    )


class ImportResponse(BaseModel):
    """Response model for bulk import operations."""

    created: int = Field(..., description="Number of items created")
    failed: int = Field(..., description="Number of items that failed")
    errors: list[str] = Field(default_factory=list, description="Error messages for failed items")


class ExportRequest(BaseModel):
    """Request model for exporting graph data."""

    format: Literal["json", "csv"] = Field(default="json", description="Export format")
    label: str | None = Field(default=None, description="Filter by label")
    include_relationships: bool = Field(default=True, description="Include relationships")
    limit: int = Field(default=1000, ge=1, le=10000, description="Maximum nodes to export")


class LinkPredictionRequest(BaseModel):
    """Request model for link prediction."""

    node_id: str = Field(..., description="Node to predict links for")
    algorithm: Literal["common_neighbors", "adamic_adar", "preferential_attachment"] = Field(
        default="common_neighbors", description="Prediction algorithm"
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum predictions")


class PredictedLinkResponse(BaseModel):
    """Response model for a predicted link."""

    target_node: GraphNodeResponse = Field(..., description="Predicted target node")
    score: float = Field(..., description="Prediction score")
    algorithm: str = Field(..., description="Algorithm used")


class LinkPredictionResponse(BaseModel):
    """Response model for link prediction results."""

    source_node_id: str
    predictions: list[PredictedLinkResponse]


class MaintenanceResponse(BaseModel):
    """Response model for maintenance operations."""

    operation: str = Field(..., description="Operation performed")
    success: bool = Field(..., description="Whether the operation succeeded")
    affected_count: int = Field(default=0, description="Number of items affected")
    message: str = Field(default="", description="Additional information")


__all__ = [
    "GraphNodeResponse",
    "GraphRelationshipResponse",
    "GraphDataResponse",
    "GraphStatsResponse",
    "NodesListResponse",
    "CreateNodeRequest",
    "UpdateNodeRequest",
    "CreateRelationshipRequest",
    "CypherExecuteRequest",
    "CypherExecuteResponse",
    "ExpandNodeRequest",
    "SearchNodesRequest",
    "ImportNodesRequest",
    "ImportRelationshipsRequest",
    "ImportResponse",
    "ExportRequest",
    "LinkPredictionRequest",
    "PredictedLinkResponse",
    "LinkPredictionResponse",
    "MaintenanceResponse",
]
