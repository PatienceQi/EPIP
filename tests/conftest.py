"""Shared pytest fixtures for the EPIP test suite."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from epip.admin import Tenant, TenantRepository, TenantStatus
from epip.api.dependencies import (
    get_entity_linker,
    get_kg_builder,
    get_neo4j_client,
    get_query_cache,
    get_query_engine,
    get_query_parser,
    get_query_planner,
    get_redis_client,
    get_tenant_repository,
)
from epip.cache import CacheStats, QueryCache
from epip.core.data_processor import DataProcessor
from epip.core.hallucination import HallucinationGuard
from epip.core.kg_builder import KGStats, KnowledgeGraphBuilder
from epip.core.query_engine import QueryEngine
from epip.db.neo4j_client import Neo4jClient
from epip.main import app
from epip.query.linker import EntityLinker, LinkedEntity
from epip.query.parser import EntityMention, ParsedQuery, QueryIntent, QueryParser
from epip.query.planner import QueryPlan, QueryPlanner, QueryStep


@pytest.fixture(scope="session")
def data_processor() -> DataProcessor:
    """Provide a reusable DataProcessor instance."""
    return DataProcessor()


@pytest.fixture(scope="session")
def hallucination_guard() -> HallucinationGuard:
    """Provide a reusable hallucination guard."""
    return HallucinationGuard()


@pytest.fixture()
def kg_builder() -> KnowledgeGraphBuilder:
    """Expose a mock KGBuilder to avoid LightRAG initialization during tests."""
    builder = MagicMock(spec=KnowledgeGraphBuilder)
    builder.configure = MagicMock()
    builder.insert_documents = AsyncMock()
    builder.query = AsyncMock(return_value="mocked-query-result")
    builder.get_statistics = AsyncMock(return_value=KGStats(0, 0, {}, {}))
    return builder


@pytest.fixture()
def query_engine(
    data_processor: DataProcessor,
    kg_builder: KnowledgeGraphBuilder,
    hallucination_guard: HallucinationGuard,
) -> QueryEngine:
    """Wire QueryEngine with mock collaborators for tests."""
    return QueryEngine(
        data_processor=data_processor,
        kg_builder=kg_builder,
        hallucination_guard=hallucination_guard,
    )


@pytest.fixture()
def _test_client_dependencies() -> dict[str, object]:
    """Common mock setup shared by the user and admin API clients."""
    mock_engine = MagicMock(spec=QueryEngine)
    mock_engine.query = AsyncMock(return_value="mocked pipeline result")
    mock_kg_builder = MagicMock(spec=KnowledgeGraphBuilder)

    mock_neo4j = MagicMock()
    mock_neo4j.ping = AsyncMock(return_value=True)

    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(return_value=True)

    mock_cache = MagicMock(spec=QueryCache)
    mock_cache.stats = AsyncMock(return_value=CacheStats(1, 1, 0.5, 2, 128))
    mock_cache.clear = AsyncMock(return_value=2)

    parsed_query = ParsedQuery(
        original="Summarize policy",
        intent=QueryIntent.FACT,
        entities=[EntityMention(text="Policy Alpha", entity_type="POLICY", start=0, end=5)],
        constraints=[],
        complexity=2,
    )

    mock_parser = MagicMock(spec=QueryParser)
    mock_parser.parse = AsyncMock(return_value=parsed_query)

    mock_linker = MagicMock(spec=EntityLinker)
    mock_linker.link = AsyncMock(
        return_value=[
            LinkedEntity(
                mention=parsed_query.entities[0],
                kg_node_id="42",
                kg_node_name="Policy Alpha",
                confidence=0.91,
                alternatives=[],
            )
        ]
    )

    plan = QueryPlan(
        query_id="test",
        parsed=parsed_query,
        linked_entities=[],
        steps=[QueryStep(step_id=1, action="search", params={}, depends_on=[])],
        estimated_cost=1.0,
    )

    mock_planner = MagicMock(spec=QueryPlanner)
    mock_planner.plan = AsyncMock(return_value=plan)
    mock_planner.to_json = MagicMock(return_value='{"plan": "test"}')

    test_tenant_repo = TenantRepository()
    test_tenant = Tenant(
        tenant_id="test-tenant",
        name="Test Tenant",
        status=TenantStatus.ACTIVE,
        config={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    admin_tenant = Tenant(
        tenant_id="admin-tenant",
        name="Admin Tenant",
        status=TenantStatus.ACTIVE,
        config={"role": "admin"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def seed_tenants() -> None:
        await test_tenant_repo.create(test_tenant)
        await test_tenant_repo.create(admin_tenant)

    asyncio.run(seed_tenants())

    app.dependency_overrides[get_query_engine] = lambda: mock_engine
    app.dependency_overrides[get_kg_builder] = lambda: mock_kg_builder
    app.dependency_overrides[get_neo4j_client] = lambda: mock_neo4j
    app.dependency_overrides[get_redis_client] = lambda: mock_redis
    app.dependency_overrides[get_query_cache] = lambda: mock_cache
    app.dependency_overrides[get_query_parser] = lambda: mock_parser
    app.dependency_overrides[get_entity_linker] = lambda: mock_linker
    app.dependency_overrides[get_query_planner] = lambda: mock_planner
    app.dependency_overrides[get_tenant_repository] = lambda: test_tenant_repo

    original_tenant_repo = getattr(app.state, "tenant_repository", None)
    app.state.tenant_repository = test_tenant_repo

    test_overrides = {
        "query_engine": mock_engine,
        "query_parser": mock_parser,
        "entity_linker": mock_linker,
        "query_planner": mock_planner,
        "kg_builder": mock_kg_builder,
        "neo4j": mock_neo4j,
        "redis": mock_redis,
        "cache": mock_cache,
        "tenant_repository": test_tenant_repo,
        "tenants": {
            test_tenant.tenant_id: test_tenant,
            admin_tenant.tenant_id: admin_tenant,
        },
    }

    try:
        yield {"test_overrides": test_overrides, "original_tenant_repo": original_tenant_repo}
    finally:
        app.dependency_overrides.clear()
        if original_tenant_repo is not None:
            app.state.tenant_repository = original_tenant_repo
        if hasattr(app.state, "test_overrides"):
            delattr(app.state, "test_overrides")


@pytest.fixture()
def api_client(_test_client_dependencies: dict[str, object]) -> TestClient:
    """Initialized FastAPI test client with mocked dependencies."""
    with TestClient(app, headers={"X-Tenant-ID": "test-tenant"}) as client:
        client.app.state.test_overrides = _test_client_dependencies["test_overrides"]
        yield client
    if hasattr(app.state, "test_overrides"):
        delattr(app.state, "test_overrides")


@pytest.fixture()
def admin_api_client(_test_client_dependencies: dict[str, object]) -> TestClient:
    """FastAPI test client authenticated as the admin tenant."""
    with TestClient(app, headers={"X-Tenant-ID": "admin-tenant"}) as client:
        client.app.state.test_overrides = _test_client_dependencies["test_overrides"]
        yield client
    if hasattr(app.state, "test_overrides"):
        delattr(app.state, "test_overrides")


@pytest.fixture()
def mock_neo4j_client(_test_client_dependencies: dict[str, object]) -> MagicMock:
    """Provide a fully mocked Neo4j client for graph API tests."""

    mock_client = MagicMock(spec=Neo4jClient)
    async_methods = [
        "get_nodes",
        "get_node",
        "get_node_relationships",
        "expand_node",
        "get_labels",
        "get_relationship_types",
        "search_nodes",
        "get_stats",
        "execute_read",
        "execute_write",
        "create_node",
        "update_node",
        "delete_node",
        "create_relationship",
        "delete_relationship",
        "ping",
    ]
    for method_name in async_methods:
        setattr(mock_client, method_name, AsyncMock())

    previous_override = app.dependency_overrides.get(get_neo4j_client)
    app.dependency_overrides[get_neo4j_client] = lambda: mock_client

    test_overrides = _test_client_dependencies["test_overrides"]
    original_neo4j_override = test_overrides.get("neo4j")
    test_overrides["neo4j"] = mock_client

    try:
        yield mock_client
    finally:
        if previous_override is not None:
            app.dependency_overrides[get_neo4j_client] = previous_override
        else:
            app.dependency_overrides.pop(get_neo4j_client, None)
        if original_neo4j_override is not None:
            test_overrides["neo4j"] = original_neo4j_override
        else:
            test_overrides.pop("neo4j", None)
