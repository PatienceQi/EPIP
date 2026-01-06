"""Tests for Cypher generation, execution, and path algorithms."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from epip.config import CypherExecutorSettings
from epip.query.algorithms import PathAlgorithms
from epip.query.cypher import CypherGenerator, CypherQuery
from epip.query.executor import CypherExecutor
from epip.query.linker import LinkedEntity
from epip.query.parser import EntityMention, ParsedQuery, QueryConstraint, QueryIntent
from epip.query.planner import QueryPlan, QueryStep


class DummyClient:
    """Simple test double for Neo4jClient."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run_cypher(self, statement: str, parameters: dict | None = None):
        payload = parameters or {}
        self.calls.append((statement, payload))
        return [
            {
                "nodes": [{"id": payload.get("start", "n-0")}],
                "relationships": [{"type": "R"}],
                "path": {"length": 1},
                "statement": statement,
                "parameters": payload,
            }
        ]


@pytest.fixture(autouse=True)
def _stub_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _sync(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("epip.query.executor.asyncio.to_thread", _sync)
    monkeypatch.setattr("epip.query.algorithms.asyncio.to_thread", _sync)


def _build_plan(intent: QueryIntent, constraints: list[QueryConstraint]) -> QueryPlan:
    mentions = [
        EntityMention(text="Org A", entity_type="ORGANIZATION", start=0, end=5),
        EntityMention(text="Policy B", entity_type="POLICY", start=6, end=14),
    ]
    linked = [
        LinkedEntity(
            mention=mentions[0],
            kg_node_id="node-a",
            kg_node_name="Org A",
            confidence=0.9,
        ),
        LinkedEntity(
            mention=mentions[1],
            kg_node_id="node-b",
            kg_node_name="Policy B",
            confidence=0.82,
        ),
    ]
    parsed = ParsedQuery(
        original="test",
        intent=intent,
        entities=mentions,
        constraints=constraints,
        complexity=2,
    )
    steps = [
        QueryStep(step_id=1, action="search", params={}, depends_on=[]),
        QueryStep(
            step_id=2,
            action="traverse",
            params={"relation": "SUPPORTED_BY", "hops": 3},
            depends_on=[1],
        ),
    ]
    return QueryPlan(
        query_id="plan-1",
        parsed=parsed,
        linked_entities=linked,
        steps=steps,
        estimated_cost=1.0,
    )


def test_cypher_generator_translates_plan() -> None:
    generator = CypherGenerator(default_timeout=4.0, default_relation="SUPPORTED_BY")
    constraints = [QueryConstraint(field="year", operator="between", value=["2020", "2021"])]
    plan = _build_plan(QueryIntent.RELATION, constraints)

    query = generator.from_plan(plan)

    assert "MATCH (n0:ORGANIZATION {id: $n0_id})" in query.statement
    assert "MATCH (n1:POLICY {id: $n1_id})" in query.statement
    assert "WHERE" in query.statement and "$n0_year_0_start" in query.statement
    assert query.parameters["n0_id"] == "node-a"
    assert query.timeout == 4.0


def test_cypher_generator_handles_missing_entities() -> None:
    plan = QueryPlan(
        query_id="plan-2",
        parsed=ParsedQuery(
            original="test",
            intent=QueryIntent.FACT,
            entities=[],
            constraints=[],
            complexity=1,
        ),
        linked_entities=[],
        steps=[],
        estimated_cost=1.0,
    )
    generator = CypherGenerator()

    query = generator.from_plan(plan)

    assert query.statement == "MATCH (n) RETURN n LIMIT 25"
    assert query.fallback is not None
    assert query.fallback.statement == "MATCH (n) RETURN n LIMIT 5"


@pytest.mark.asyncio
async def test_cypher_executor_executes_query() -> None:
    client = DummyClient()
    executor = CypherExecutor(client, settings=CypherExecutorSettings(timeout=0.0, max_retries=0))
    query = CypherQuery(statement="RETURN 1", parameters={}, timeout=0.0)

    result = await executor.execute(query)

    assert not result.timed_out
    assert result.nodes == [{"id": "n-0"}]
    assert result.relations == [{"type": "R"}]
    assert result.paths == [{"length": 1}]


@pytest.mark.asyncio
async def test_execute_with_fallback_retries_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DummyClient()
    executor = CypherExecutor(client, settings=CypherExecutorSettings(timeout=0.0, max_retries=2))
    fallback_query = CypherQuery(statement="MATCH (n) RETURN n", parameters={}, timeout=0.0)
    primary = CypherQuery(statement="SLOW", parameters={}, timeout=0.0, fallback=fallback_query)
    statements: list[str] = []

    async def fake_run(statement: str, *_args, **_kwargs):
        statements.append(statement)
        if statement == "SLOW":
            raise asyncio.TimeoutError
        return [
            {
                "nodes": [{"id": "fallback"}],
                "relationships": [],
                "path": None,
            }
        ]

    monkeypatch.setattr(executor, "_run_with_timeout", fake_run)

    result = await executor.execute_with_fallback(primary)

    assert statements == ["SLOW", "MATCH (n) RETURN n"]
    assert result.nodes == [{"id": "fallback"}]
    assert not result.timed_out


@pytest.mark.asyncio
async def test_shortest_path_delegates_to_algorithms(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DummyClient()
    executor = CypherExecutor(client)
    dijkstra = AsyncMock(return_value=[{"cost": 1}])
    astar = AsyncMock(return_value=[{"cost": 2}])
    all_paths = AsyncMock(return_value=[[{"node": "a"}]])

    monkeypatch.setattr(PathAlgorithms, "dijkstra", dijkstra)
    monkeypatch.setattr(PathAlgorithms, "astar", astar)
    monkeypatch.setattr(PathAlgorithms, "all_shortest_paths", all_paths)

    assert await executor.shortest_path("s", "e", algorithm="dijkstra") == [{"cost": 1}]
    dijkstra.assert_awaited_once_with(client, "s", "e", weight_property="weight")

    assert await executor.shortest_path("s", "e", algorithm="astar") == [{"cost": 2}]
    astar.assert_awaited_once_with(client, "s", "e", heuristic="euclidean")

    assert await executor.shortest_path("s", "e") == [{"path": [{"node": "a"}]}]
    all_paths.assert_awaited_once_with(client, "s", "e", max_paths=3)


@pytest.mark.asyncio
async def test_path_algorithms_build_statements() -> None:
    client = DummyClient()

    await PathAlgorithms.dijkstra(client, "start", "end", weight_property="capacity")
    assert "gds.shortestPath.dijkstra.stream" in client.calls[-1][0]
    assert client.calls[-1][1] == {"start": "start", "end": "end", "weight": "capacity"}

    await PathAlgorithms.all_shortest_paths(client, "start", "end", max_paths=2)
    statement, params = client.calls[-1]
    assert "gds.shortestPath.yens.stream" in statement
    assert params["max_paths"] == 2
