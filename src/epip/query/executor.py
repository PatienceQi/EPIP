"""Cypher query execution utilities on top of the Neo4j client."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from epip.config import CypherExecutorSettings
from epip.db import Neo4jClient

from .algorithms import PathAlgorithms
from .cypher import CypherQuery

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class QueryResult:
    """Normalized representation of a Cypher query response."""

    nodes: list[Any] = field(default_factory=list)
    relations: list[Any] = field(default_factory=list)
    paths: list[Any] = field(default_factory=list)
    execution_time: float = 0.0
    timed_out: bool = False


class CypherExecutor:
    """Execute Cypher queries with timeout handling and fallbacks."""

    def __init__(
        self,
        client: Neo4jClient,
        *,
        settings: CypherExecutorSettings | None = None,
    ) -> None:
        self._client = client
        self._settings = settings or CypherExecutorSettings()

    async def execute(self, query: CypherQuery) -> QueryResult:
        """Execute a Cypher query respecting configured timeout."""
        timeout = query.timeout or self._settings.timeout
        start = time.perf_counter()
        try:
            records = await self._run_with_timeout(query.statement, query.parameters, timeout)
            elapsed = time.perf_counter() - start
            return self._build_result(records, elapsed, timed_out=False)
        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - start
            logger.warning("Cypher execution timed out", statement=query.statement)
            return QueryResult(execution_time=elapsed, timed_out=True)

    async def execute_with_fallback(self, query: CypherQuery) -> QueryResult:
        """Run a Cypher query and retry with fallbacks if necessary."""
        retries = 0
        current = query
        last_result: QueryResult | None = None
        while current and retries <= self._settings.max_retries:
            result = await self.execute(current)
            if not result.timed_out:
                return result
            last_result = result
            current = current.fallback
            retries += 1
        return last_result or QueryResult(timed_out=True)

    async def shortest_path(
        self,
        start_id: str,
        end_id: str,
        algorithm: str = "all_shortest_paths",
    ) -> list[dict[str, Any]]:
        """Execute a Graph Data Science shortest path algorithm."""
        algorithm_key = (algorithm or "all_shortest_paths").lower()
        if algorithm_key == "dijkstra":
            return await PathAlgorithms.dijkstra(
                self._client,
                start_id,
                end_id,
                weight_property="weight",
            )
        if algorithm_key == "astar":
            return await PathAlgorithms.astar(
                self._client,
                start_id,
                end_id,
                heuristic="euclidean",
            )
        paths = await PathAlgorithms.all_shortest_paths(
            self._client,
            start_id,
            end_id,
            max_paths=3,
        )
        return [{"path": path} for path in paths]

    async def _run_with_timeout(
        self,
        statement: str,
        parameters: dict[str, Any] | None,
        timeout: float | None,
    ) -> list[dict[str, Any]]:
        if timeout and timeout > 0:
            return await asyncio.wait_for(
                asyncio.to_thread(self._client.run_cypher, statement, parameters or {}),
                timeout=timeout,
            )
        return await asyncio.to_thread(self._client.run_cypher, statement, parameters or {})

    def _build_result(
        self,
        records: list[dict[str, Any]],
        elapsed: float,
        *,
        timed_out: bool,
    ) -> QueryResult:
        nodes: list[Any] = []
        relations: list[Any] = []
        paths: list[Any] = []

        for record in records:
            if "nodes" in record:
                nodes.extend(record["nodes"])
            if "relationships" in record:
                relations.extend(record["relationships"])
            if "path" in record:
                paths.append(record["path"])
        return QueryResult(
            nodes=nodes,
            relations=relations,
            paths=paths,
            execution_time=elapsed,
            timed_out=timed_out,
        )
