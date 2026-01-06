"""Client wrapper for interacting with Neo4j."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import Neo4jError
except ImportError:  # pragma: no cover - optional dependency
    GraphDatabase = None  # type: ignore[assignment]
    Neo4jError = Exception


@dataclass
class GraphNode:
    """Represents a Neo4j node."""

    id: str
    labels: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphRelationship:
    """Represents a Neo4j relationship."""

    id: str
    type: str
    start_node_id: str
    end_node_id: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphStats:
    """Statistics about the graph database."""

    node_count: int = 0
    relationship_count: int = 0
    label_counts: dict[str, int] = field(default_factory=dict)
    relationship_type_counts: dict[str, int] = field(default_factory=dict)


class Neo4jClient:
    """Manage the lifecycle of the Neo4j driver."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._driver: Any | None = None

    def connect(self) -> None:
        """Create the driver handle."""
        if self._driver is not None:
            return

        if GraphDatabase is None:
            self._driver = object()
            return

        self._driver = GraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
        )

    def close(self) -> None:
        """Dispose of the underlying driver."""
        driver, self._driver = self._driver, None
        if driver is None:
            return

        close = getattr(driver, "close", None)
        if callable(close):
            close()

    def _ensure_connected(self) -> None:
        """Ensure the driver is connected."""
        if self._driver is None:
            self.connect()
        if self._driver is None:
            raise RuntimeError("Neo4j driver is not initialized")

    def run_cypher(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a Cypher statement synchronously."""
        self._ensure_connected()

        if GraphDatabase is None or not hasattr(self._driver, "session"):
            return []

        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    async def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read-only Cypher query asynchronously."""
        return await asyncio.to_thread(self.run_cypher, query, parameters)

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a write Cypher query asynchronously."""
        return await asyncio.to_thread(self.run_cypher, query, parameters)

    async def ping(self) -> bool:
        """Check connectivity against the configured Neo4j instance."""
        if self._driver is None:
            self.connect()

        driver = self._driver
        if driver is None:
            return False

        if GraphDatabase is None or not hasattr(driver, "verify_connectivity"):
            return True

        return await asyncio.to_thread(self._verify_connectivity, driver)

    @staticmethod
    def _verify_connectivity(driver: Any) -> bool:
        try:
            driver.verify_connectivity()
            return True
        except Neo4jError:
            return False
        except Exception:
            return False

    async def get_labels(self) -> list[str]:
        """Get all node labels in the database."""
        query = "CALL db.labels() YIELD label RETURN label"
        result = await self.execute_read(query)
        return [r["label"] for r in result]

    async def get_relationship_types(self) -> list[str]:
        """Get all relationship types in the database."""
        query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        result = await self.execute_read(query)
        return [r["relationshipType"] for r in result]

    async def get_stats(self) -> GraphStats:
        """Get graph statistics."""
        stats = GraphStats()

        node_count_result = await self.execute_read("MATCH (n) RETURN count(n) as count")
        if node_count_result:
            stats.node_count = node_count_result[0].get("count", 0)

        rel_count_result = await self.execute_read("MATCH ()-[r]->() RETURN count(r) as count")
        if rel_count_result:
            stats.relationship_count = rel_count_result[0].get("count", 0)

        label_counts_result = await self.execute_read(
            "CALL db.labels() YIELD label "
            "CALL { WITH label MATCH (n) WHERE label IN labels(n) RETURN count(n) as count } "
            "RETURN label, count"
        )
        stats.label_counts = {r["label"]: r["count"] for r in label_counts_result}

        rel_type_counts_result = await self.execute_read(
            "CALL db.relationshipTypes() YIELD relationshipType "
            "CALL { WITH relationshipType MATCH ()-[r]->() WHERE type(r) = relationshipType RETURN count(r) as count } "
            "RETURN relationshipType, count"
        )
        stats.relationship_type_counts = {r["relationshipType"]: r["count"] for r in rel_type_counts_result}

        return stats

    async def get_nodes(
        self,
        label: str | None = None,
        limit: int = 50,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[GraphNode]:
        """Get nodes with optional filtering."""
        label_clause = f":{label}" if label else ""
        where_clauses = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if filters:
            for i, (key, value) in enumerate(filters.items()):
                param_name = f"filter_{i}"
                where_clauses.append(f"n.{key} = ${param_name}")
                params[param_name] = value

        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            MATCH (n{label_clause})
            {where_str}
            RETURN elementId(n) as id, labels(n) as labels, properties(n) as properties
            SKIP $offset LIMIT $limit
        """
        result = await self.execute_read(query, params)
        return [
            GraphNode(id=r["id"], labels=r["labels"], properties=r["properties"])
            for r in result
        ]

    async def get_node(self, node_id: str) -> GraphNode | None:
        """Get a single node by ID."""
        query = """
            MATCH (n) WHERE elementId(n) = $id
            RETURN elementId(n) as id, labels(n) as labels, properties(n) as properties
        """
        result = await self.execute_read(query, {"id": node_id})
        if not result:
            return None
        r = result[0]
        return GraphNode(id=r["id"], labels=r["labels"], properties=r["properties"])

    async def create_node(self, labels: list[str], properties: dict[str, Any]) -> GraphNode:
        """Create a new node."""
        label_str = ":".join(labels) if labels else "Node"
        query = f"""
            CREATE (n:{label_str} $properties)
            RETURN elementId(n) as id, labels(n) as labels, properties(n) as properties
        """
        result = await self.execute_write(query, {"properties": properties})
        r = result[0]
        return GraphNode(id=r["id"], labels=r["labels"], properties=r["properties"])

    async def update_node(self, node_id: str, properties: dict[str, Any]) -> GraphNode | None:
        """Update node properties."""
        query = """
            MATCH (n) WHERE elementId(n) = $id
            SET n += $properties
            RETURN elementId(n) as id, labels(n) as labels, properties(n) as properties
        """
        result = await self.execute_write(query, {"id": node_id, "properties": properties})
        if not result:
            return None
        r = result[0]
        return GraphNode(id=r["id"], labels=r["labels"], properties=r["properties"])

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its relationships."""
        query = "MATCH (n) WHERE elementId(n) = $id DETACH DELETE n RETURN count(n) as deleted"
        result = await self.execute_write(query, {"id": node_id})
        return bool(result and result[0].get("deleted", 0) > 0)

    async def get_node_relationships(
        self, node_id: str, direction: str = "both", rel_type: str | None = None
    ) -> list[GraphRelationship]:
        """Get relationships for a node."""
        type_filter = f":{rel_type}" if rel_type else ""

        if direction == "outgoing":
            pattern = f"(n)-[r{type_filter}]->(m)"
        elif direction == "incoming":
            pattern = f"(n)<-[r{type_filter}]-(m)"
        else:
            pattern = f"(n)-[r{type_filter}]-(m)"

        query = f"""
            MATCH {pattern} WHERE elementId(n) = $id
            RETURN elementId(r) as id, type(r) as type,
                   elementId(startNode(r)) as start_id, elementId(endNode(r)) as end_id,
                   properties(r) as properties
        """
        result = await self.execute_read(query, {"id": node_id})
        return [
            GraphRelationship(
                id=r["id"],
                type=r["type"],
                start_node_id=r["start_id"],
                end_node_id=r["end_id"],
                properties=r["properties"],
            )
            for r in result
        ]

    async def expand_node(self, node_id: str, depth: int = 1) -> tuple[list[GraphNode], list[GraphRelationship]]:
        """Expand a node to get its neighbors up to a certain depth."""
        query = f"""
            MATCH path = (n)-[*1..{depth}]-(m) WHERE elementId(n) = $id
            WITH collect(DISTINCT m) as nodes, collect(DISTINCT relationships(path)) as rels_list
            UNWIND nodes as node
            WITH collect(DISTINCT {{
                id: elementId(node),
                labels: labels(node),
                properties: properties(node)
            }}) as node_data, rels_list
            UNWIND rels_list as rels
            UNWIND rels as rel
            WITH node_data, collect(DISTINCT {{
                id: elementId(rel),
                type: type(rel),
                start_id: elementId(startNode(rel)),
                end_id: elementId(endNode(rel)),
                properties: properties(rel)
            }}) as rel_data
            RETURN node_data, rel_data
        """
        result = await self.execute_read(query, {"id": node_id})
        if not result:
            return [], []

        r = result[0]
        nodes = [GraphNode(id=n["id"], labels=n["labels"], properties=n["properties"]) for n in r.get("node_data", [])]
        relationships = [
            GraphRelationship(
                id=rel["id"],
                type=rel["type"],
                start_node_id=rel["start_id"],
                end_node_id=rel["end_id"],
                properties=rel["properties"],
            )
            for rel in r.get("rel_data", [])
        ]
        return nodes, relationships

    async def create_relationship(
        self,
        start_node_id: str,
        end_node_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> GraphRelationship:
        """Create a relationship between two nodes."""
        query = f"""
            MATCH (a), (b)
            WHERE elementId(a) = $start_id AND elementId(b) = $end_id
            CREATE (a)-[r:{rel_type} $properties]->(b)
            RETURN elementId(r) as id, type(r) as type,
                   elementId(startNode(r)) as start_id, elementId(endNode(r)) as end_id,
                   properties(r) as properties
        """
        result = await self.execute_write(
            query,
            {"start_id": start_node_id, "end_id": end_node_id, "properties": properties or {}},
        )
        r = result[0]
        return GraphRelationship(
            id=r["id"],
            type=r["type"],
            start_node_id=r["start_id"],
            end_node_id=r["end_id"],
            properties=r["properties"],
        )

    async def delete_relationship(self, rel_id: str) -> bool:
        """Delete a relationship."""
        query = "MATCH ()-[r]->() WHERE elementId(r) = $id DELETE r RETURN count(r) as deleted"
        result = await self.execute_write(query, {"id": rel_id})
        return bool(result and result[0].get("deleted", 0) > 0)

    async def search_nodes(
        self, query_text: str, label: str | None = None, limit: int = 20
    ) -> list[GraphNode]:
        """Search nodes by property values."""
        label_clause = f":{label}" if label else ""
        query = f"""
            MATCH (n{label_clause})
            WHERE any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS $query)
            RETURN elementId(n) as id, labels(n) as labels, properties(n) as properties
            LIMIT $limit
        """
        result = await self.execute_read(query, {"query": query_text, "limit": limit})
        return [
            GraphNode(id=r["id"], labels=r["labels"], properties=r["properties"])
            for r in result
        ]
