"""Dependency wiring helpers for FastAPI routes."""

from functools import lru_cache

from epip.admin import TenantRepository
from epip.cache import CacheConfig, QueryCache
from epip.config import Settings
from epip.config import get_settings as load_settings
from epip.core.data_processor import DataProcessor
from epip.core.hallucination import HallucinationGuard
from epip.core.kg_builder import KnowledgeGraphBuilder
from epip.core.query_engine import QueryEngine
from epip.db import Neo4jClient, RedisClient
from epip.query.linker import EntityLinker
from epip.query.parser import QueryParser
from epip.query.planner import QueryPlanner
from epip.visualization import VisualizationDataGenerator

# Lazy import to avoid circular dependency
_visualization_store = None


def _get_visualization_memory_store():
    """Lazy import and singleton for VisualizationMemoryStore."""
    global _visualization_store
    if _visualization_store is None:
        from epip.api.visualization import VisualizationMemoryStore
        _visualization_store = VisualizationMemoryStore()
    return _visualization_store


def get_settings() -> Settings:
    """Expose cached application settings for the API layer."""
    return load_settings()


@lru_cache
def get_neo4j_client() -> Neo4jClient:
    """Provide a shared Neo4j client instance."""
    cfg = get_settings()
    client = Neo4jClient(cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password)
    client.connect()
    return client


@lru_cache
def get_redis_client() -> RedisClient:
    """Provide a shared Redis client instance."""
    cfg = get_settings()
    client = RedisClient(cfg.redis_url)
    client.connect()
    return client


@lru_cache
def get_data_processor() -> DataProcessor:
    """Instantiate the shared data processor component."""
    return DataProcessor()


@lru_cache
def get_kg_builder() -> KnowledgeGraphBuilder:
    """Instantiate the shared knowledge graph builder."""
    return KnowledgeGraphBuilder()


@lru_cache
def get_hallucination_guard() -> HallucinationGuard:
    """Instantiate the shared hallucination mitigation component."""
    return HallucinationGuard()


@lru_cache
def get_query_engine() -> QueryEngine:
    """Provide a cached query engine instance for request handlers."""
    return QueryEngine(
        data_processor=get_data_processor(),
        kg_builder=get_kg_builder(),
        hallucination_guard=get_hallucination_guard(),
    )


@lru_cache
def get_query_parser() -> QueryParser:
    """Expose a shared QueryParser for API usage."""
    return QueryParser()


@lru_cache
def get_entity_linker() -> EntityLinker:
    """Reuse a single EntityLinker instance to avoid reloading embeddings."""
    return EntityLinker()


@lru_cache
def get_query_planner() -> QueryPlanner:
    """Provide the query planner for request handlers."""
    return QueryPlanner()


@lru_cache
def get_query_cache() -> QueryCache:
    """Expose a shared query cache configured via app settings."""
    cfg = get_settings()
    return QueryCache(CacheConfig(redis_url=cfg.redis_url))


@lru_cache
def get_visualization_generator() -> VisualizationDataGenerator:
    """Provide a shared visualization data generator."""
    return VisualizationDataGenerator()


def get_visualization_store():
    """Provide the shared visualization memory store."""
    return _get_visualization_memory_store()


@lru_cache
def get_tenant_repository() -> TenantRepository:
    """Provide a shared tenant repository instance."""
    return TenantRepository()


__all__ = [
    "get_settings",
    "get_neo4j_client",
    "get_redis_client",
    "get_data_processor",
    "get_kg_builder",
    "get_hallucination_guard",
    "get_query_engine",
    "get_query_parser",
    "get_entity_linker",
    "get_query_planner",
    "get_query_cache",
    "get_visualization_generator",
    "get_visualization_store",
    "get_tenant_repository",
]
