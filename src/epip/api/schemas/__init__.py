"""API schema models."""

from typing import Literal

from pydantic import BaseModel, Field

from .graph import *  # noqa: F401, F403
from .graph import __all__ as graph_all


class StatusResponse(BaseModel):
    """Metadata returned by the status endpoint."""

    environment: str = Field(..., description="Deployment environment name")
    version: str = Field(..., description="Version of the EPIP service")


class QueryRequest(BaseModel):
    """LLM-powered query request payload."""

    query: str = Field(..., description="Natural language question to evaluate")
    source: str = Field(default="api", description="Source system initiating the query")


class QueryResponse(BaseModel):
    """Response returned by the orchestration pipeline."""

    result: str = Field(..., description="Aggregated insight for the query")
    metadata: dict[str, str] = Field(default_factory=dict, description="Lightweight trace metadata")


class ServiceStatus(BaseModel):
    """Health state for core infrastructure services."""

    neo4j: Literal["up", "down"] = Field(..., description="Neo4j availability flag")
    redis: Literal["up", "down"] = Field(..., description="Redis availability flag")


class HealthResponse(BaseModel):
    """Response payload for the health endpoint."""

    status: Literal["healthy", "unhealthy"] = Field(..., description="Overall service status")
    services: ServiceStatus = Field(..., description="Per-service health details")


class CacheStatsResponse(BaseModel):
    """Serialized cache statistics returned via the API."""

    hits: int = Field(..., description="Number of cache hits since startup")
    misses: int = Field(..., description="Number of cache misses since startup")
    hit_rate: float = Field(..., description="Hit ratio computed from hits/misses")
    size: int = Field(..., description="Number of cached entries tracked via the backend")
    memory_usage: int = Field(..., description="Approximate memory usage reported by the backend")


class CacheClearRequest(BaseModel):
    """Cache clear payload."""

    pattern: str = Field("*", description="Glob pattern relative to the cache prefix")


class CacheClearResponse(BaseModel):
    """Cache clear outcome payload."""

    pattern: str = Field(..., description="Pattern that was cleared")
    cleared: int = Field(..., description="Number of entries removed from the cache")


__all__ = [
    "StatusResponse",
    "QueryRequest",
    "QueryResponse",
    "ServiceStatus",
    "HealthResponse",
    "CacheStatsResponse",
    "CacheClearRequest",
    "CacheClearResponse",
] + graph_all
