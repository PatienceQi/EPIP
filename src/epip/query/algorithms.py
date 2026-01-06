"""Cypher snippets for Neo4j GDS path algorithms."""

from __future__ import annotations

import asyncio
from typing import Any

from epip.db import Neo4jClient


class PathAlgorithms:
    """Generate Cypher statements for common path algorithms."""

    @staticmethod
    async def dijkstra(
        driver: Neo4jClient,
        start: str,
        end: str,
        weight_property: str = "weight",
    ) -> list[dict[str, Any]]:
        statement = (
            "CALL gds.shortestPath.dijkstra.stream('kg-graph', {"
            "sourceNode: gds.util.asNodeId($start), "
            "targetNode: gds.util.asNodeId($end), "
            "relationshipWeightProperty: $weight"
            "}) "
            "YIELD sourceNode, targetNode, totalCost, nodeIds, costs "
            "RETURN sourceNode, targetNode, totalCost, nodeIds, costs"
        )
        return await PathAlgorithms._run(
            driver,
            statement,
            {"start": start, "end": end, "weight": weight_property},
        )

    @staticmethod
    async def astar(
        driver: Neo4jClient,
        start: str,
        end: str,
        heuristic: str = "euclidean",
    ) -> list[dict[str, Any]]:
        statement = (
            "CALL gds.shortestPath.astar.stream('kg-graph', {"
            "sourceNode: gds.util.asNodeId($start), "
            "targetNode: gds.util.asNodeId($end), "
            "latitudeProperty: 'lat', longitudeProperty: 'lon', "
            "relationshipWeightProperty: 'weight'"
            "}) "
            "YIELD nodeIds, path "
            "RETURN nodeIds, path"
        )
        return await PathAlgorithms._run(
            driver,
            statement,
            {"start": start, "end": end, "heuristic": heuristic},
        )

    @staticmethod
    async def all_shortest_paths(
        driver: Neo4jClient,
        start: str,
        end: str,
        max_paths: int = 3,
    ) -> list[list[dict[str, Any]]]:
        statement = (
            "CALL gds.shortestPath.yens.stream('kg-graph', {"
            "sourceNode: gds.util.asNodeId($start), "
            "targetNode: gds.util.asNodeId($end), "
            "k: $max_paths"
            "}) "
            "YIELD index, path "
            "RETURN path"
        )
        records = await PathAlgorithms._run(
            driver,
            statement,
            {"start": start, "end": end, "max_paths": max_paths},
        )
        result: list[list[dict[str, Any]]] = []
        for record in records:
            path = record.get("path")
            if path is not None:
                result.append(path)
        return result

    @staticmethod
    async def _run(
        driver: Neo4jClient,
        statement: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(driver.run_cypher, statement, params)
