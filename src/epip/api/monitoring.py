"""Monitoring endpoints exposing system health and Prometheus metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from epip.api.dependencies import get_neo4j_client, get_redis_client
from epip.db import Neo4jClient, RedisClient
from epip.monitoring.metrics import metrics_collector

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/metrics", response_class=Response)
async def get_metrics() -> Response:
    """Expose Prometheus metrics in the text exposition format."""
    data = metrics_collector.get_metrics()
    return Response(content=data, media_type="text/plain; version=0.0.4")


@router.get("/health/live")
async def liveness_probe() -> dict[str, str]:
    """Liveness check that only confirms the application is running."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_probe(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
    redis: RedisClient = Depends(get_redis_client),
) -> dict[str, str]:
    """Readiness check that validates downstream dependencies."""
    neo4j_ok, redis_ok = await neo4j.ping(), await redis.ping()
    status = "ok" if neo4j_ok and redis_ok else "error"
    return {
        "status": status,
        "neo4j": "up" if neo4j_ok else "down",
        "redis": "up" if redis_ok else "down",
    }


__all__ = ["router"]
