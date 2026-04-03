"""Relation extraction utilities and graph health diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from epip.core.kg_builder import KGBuilder

logger = structlog.get_logger()

try:  # Optional dependencies resolved at runtime
    from lightrag.kg.neo4j_impl import Neo4JStorage
except Exception:  # pragma: no cover - neo4j backend is optional in tests
    Neo4JStorage = None  # type: ignore

try:
    from lightrag.kg.networkx_impl import NetworkXStorage
except Exception:  # pragma: no cover - networkx backend may be absent
    NetworkXStorage = None  # type: ignore


@dataclass(slots=True)
class RelationExtractionConfig:
    """Configuration controlling relation analysis and reporting."""

    confidence_threshold: float = 0.5
    relation_types: list[str] = field(
        default_factory=lambda: [
            "ASSOCIATED_WITH",
            "SUPPORTED_BY",
            "FUNDED_BY",
            "COORDINATES_WITH",
            "LOCATED_IN",
        ]
    )
    default_relation_type: str = "ASSOCIATED_WITH"
    report_sample_size: int = 25


@dataclass(slots=True)
class SubgraphInfo:
    """Summary of graph connectivity metrics."""

    node_count: int
    edge_count: int
    is_connected: bool
    component_count: int


@dataclass(slots=True)
class RelationReport:
    """Aggregated relation statistics."""

    total_relations: int
    relation_type_counts: dict[str, int]
    low_confidence_count: int
    average_confidence: float
    sample_relations: list[dict[str, Any]]


@dataclass(slots=True)
class GraphHealthReport:
    """High-level health summary for the LightRAG graph."""

    subgraph: SubgraphInfo
    isolated_nodes: list[str]
    bridge_suggestions: list[tuple[str, str, str]]


@dataclass(slots=True)
class _GraphSnapshot:
    """Internal container describing the KG nodes and edges."""

    nodes: dict[str, dict[str, Any]]
    edges: list[tuple[str, str, dict[str, Any]]]

    def adjacency(self) -> dict[str, set[str]]:
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in self.nodes}
        for source, target, _ in self.edges:
            if source in adjacency:
                adjacency[source].add(target)
            if target in adjacency:
                adjacency[target].add(source)
        return adjacency

    def node_name(self, node_id: str) -> str:
        payload = self.nodes.get(node_id) or {}
        candidate = payload.get("name") or payload.get("entity_name")
        return str(candidate or node_id)


async def _resolve_storage(kg_builder: KGBuilder) -> Any | None:
    require_rag = getattr(kg_builder, "_require_rag", None)
    ensure_initialized = getattr(kg_builder, "_ensure_initialized", None)
    if not callable(require_rag) or not callable(ensure_initialized):
        logger.warning("KGBuilder is not ready; storage unavailable for analysis")
        return None
    rag = require_rag()
    await ensure_initialized()
    return getattr(rag, "chunk_entity_relation_graph", None)


async def _get_graph_snapshot(kg_builder: KGBuilder) -> _GraphSnapshot:
    storage = await _resolve_storage(kg_builder)
    if storage is None:
        return _GraphSnapshot(nodes={}, edges=[])

    if NetworkXStorage and isinstance(storage, NetworkXStorage):
        return await _snapshot_from_networkx(storage)
    if Neo4JStorage and isinstance(storage, Neo4JStorage):
        return await _snapshot_from_neo4j(storage)

    if hasattr(storage, "_get_graph"):
        return await _snapshot_from_networkx(storage)
    if hasattr(storage, "_driver") and hasattr(storage, "_get_workspace_label"):
        return await _snapshot_from_neo4j(storage)

    logger.warning(
        "Unsupported graph storage; cannot collect snapshot",
        backend=type(storage).__name__,
    )
    return _GraphSnapshot(nodes={}, edges=[])


async def _snapshot_from_networkx(storage) -> _GraphSnapshot:
    graph = await storage._get_graph()
    nodes: dict[str, dict[str, Any]] = {}
    for node_id, data in graph.nodes(data=True):
        node_key = str(node_id)
        nodes[node_key] = dict(data)
        nodes[node_key].setdefault("name", data.get("entity_name") or node_key)

    edges: list[tuple[str, str, dict[str, Any]]] = []
    for source, target, attributes in graph.edges(data=True):
        relation_type = attributes.get("relation_type") or attributes.get("type") or "RELATED_TO"
        confidence = float(attributes.get("confidence") or 0.0)
        edges.append(
            (
                str(source),
                str(target),
                {
                    "relation_type": relation_type,
                    "confidence": confidence,
                },
            )
        )
    return _GraphSnapshot(nodes=nodes, edges=edges)


async def _snapshot_from_neo4j(storage) -> _GraphSnapshot:
    if getattr(storage, "_driver", None) is None:
        await storage.initialize()
    driver = getattr(storage, "_driver", None)
    if driver is None:  # pragma: no cover - depends on Neo4j availability
        return _GraphSnapshot(nodes={}, edges=[])
    label = storage._get_workspace_label()
    database = getattr(storage, "_DATABASE", None)

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str, dict[str, Any]]] = []

    async with driver.session(database=database, default_access_mode="READ") as session:
        node_query = (
            f"MATCH (n:`{label}`) "
            "RETURN id(n) AS id, coalesce(n.name, n.entity_name, toString(id(n))) AS name"
        )
        node_result = await session.run(node_query)
        async for row in node_result:
            nodes[str(row["id"])] = {"name": row["name"]}

        edge_query = f"""
        MATCH (src:`{label}`)-[r:DIRECTED]->(dst:`{label}`)
        RETURN id(src) AS source,
               id(dst) AS target,
               coalesce(r.relation_type, 'RELATED_TO') AS relation_type,
               coalesce(r.confidence, 0.0) AS confidence
        """
        edge_result = await session.run(edge_query)
        async for row in edge_result:
            edges.append(
                (
                    str(row["source"]),
                    str(row["target"]),
                    {
                        "relation_type": row["relation_type"],
                        "confidence": float(row["confidence"]),
                    },
                )
            )

    return _GraphSnapshot(nodes=nodes, edges=edges)


class SubgraphAnalyzer:
    """Compute structural information about LightRAG knowledge graphs."""

    def __init__(self, config: RelationExtractionConfig | None = None) -> None:
        self.config = config or RelationExtractionConfig()

    async def analyze_connectivity(self, kg_builder: KGBuilder) -> SubgraphInfo:
        snapshot = await _get_graph_snapshot(kg_builder)
        adjacency = snapshot.adjacency()
        components = self._connected_components(adjacency)
        component_count = len(components)
        node_count = len(snapshot.nodes)
        edge_count = len(snapshot.edges)
        is_connected = node_count == 0 or component_count == 1
        return SubgraphInfo(
            node_count=node_count,
            edge_count=edge_count,
            is_connected=is_connected,
            component_count=component_count,
        )

    async def find_isolated_nodes(self, kg_builder: KGBuilder) -> list[str]:
        snapshot = await _get_graph_snapshot(kg_builder)
        adjacency = snapshot.adjacency()
        isolates = [
            snapshot.node_name(node_id) for node_id, neighbors in adjacency.items() if not neighbors
        ]
        isolates.sort()
        return isolates

    async def suggest_bridges(
        self, kg_builder: KGBuilder, max_suggestions: int = 5
    ) -> list[tuple[str, str, str]]:
        if max_suggestions <= 0:
            return []
        snapshot = await _get_graph_snapshot(kg_builder)
        adjacency = snapshot.adjacency()
        components = self._connected_components(adjacency)
        if len(components) <= 1:
            return []

        representatives: list[str] = []
        for component in components:
            representative = self._select_representative(component, adjacency)
            if representative is not None:
                representatives.append(representative)

        suggestions: list[tuple[str, str, str]] = []
        for left, right in zip(representatives, representatives[1:]):
            relation_type = self.config.default_relation_type
            suggestions.append(
                (
                    snapshot.node_name(left),
                    relation_type,
                    snapshot.node_name(right),
                )
            )
            if len(suggestions) >= max_suggestions:
                break
        return suggestions

    @staticmethod
    def _connected_components(adjacency: dict[str, set[str]]) -> list[list[str]]:
        visited: set[str] = set()
        components: list[list[str]] = []
        for node_id in adjacency:
            if node_id in visited:
                continue
            stack = [node_id]
            component: list[str] = []
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                stack.extend(neighbor for neighbor in adjacency[current] if neighbor not in visited)
            components.append(component)
        return components

    @staticmethod
    def _select_representative(component: list[str], adjacency: dict[str, set[str]]) -> str | None:
        if not component:
            return None
        return max(component, key=lambda node: len(adjacency.get(node, ())))


class RelationReportGenerator:
    """Compile textual reports describing LightRAG relations."""

    def __init__(self, config: RelationExtractionConfig | None = None) -> None:
        self.config = config or RelationExtractionConfig()

    async def generate_report(self, kg_builder: KGBuilder) -> RelationReport:
        stats = await kg_builder.get_statistics()
        sample, low_confidence, avg_confidence = await self._collect_relation_samples(
            kg_builder,
            limit=self.config.report_sample_size,
        )
        return RelationReport(
            total_relations=stats.total_relations,
            relation_type_counts=stats.relation_types,
            low_confidence_count=low_confidence,
            average_confidence=avg_confidence,
            sample_relations=sample,
        )

    async def _collect_relation_samples(
        self, kg_builder: KGBuilder, *, limit: int
    ) -> tuple[list[dict[str, Any]], int, float]:
        snapshot = await _get_graph_snapshot(kg_builder)
        if not snapshot.edges:
            return [], 0, 0.0

        edges_sorted = sorted(
            snapshot.edges,
            key=lambda edge: float(edge[2].get("confidence", 0.0)),
            reverse=True,
        )
        sample: list[dict[str, Any]] = []
        take = len(edges_sorted) if limit <= 0 else min(limit, len(edges_sorted))
        for source, target, attributes in edges_sorted[:take]:
            sample.append(
                {
                    "source": snapshot.node_name(source),
                    "target": snapshot.node_name(target),
                    "relation_type": attributes.get("relation_type", "RELATED_TO"),
                    "confidence": float(attributes.get("confidence", 0.0)),
                }
            )

        confidences = [
            float(attributes.get("confidence", 0.0)) for _, _, attributes in snapshot.edges
        ]
        low_confidence = sum(
            1 for confidence in confidences if confidence < self.config.confidence_threshold
        )
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return sample, low_confidence, avg_confidence

    def export_markdown(self, report: RelationReport, output_path: Path) -> Path:
        """Persist the relation report to disk as Markdown."""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Relation Analysis Report", ""]
        lines.append(f"Total relations: {report.total_relations}")
        lines.append(
            f"Low confidence relations (<{self.config.confidence_threshold}): "
            f"{report.low_confidence_count}"
        )
        lines.append(f"Average confidence: {report.average_confidence:.2f}")
        lines.append("")
        lines.append("## Relation Types")
        for relation_type, count in sorted(report.relation_type_counts.items()):
            lines.append(f"- {relation_type}: {count}")
        lines.append("")
        lines.append("## Sample Relations")
        for relation in report.sample_relations:
            lines.append(
                f"- **{relation['source']}** --{relation['relation_type']}--> "
                f"**{relation['target']}** (confidence={relation['confidence']:.2f})"
            )
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Relation report exported", path=str(output_path))
        return output_path


class GraphValidator:
    """Validate graph structure and optionally repair isolated components."""

    def __init__(self, analyzer: SubgraphAnalyzer | None = None) -> None:
        self.analyzer = analyzer or SubgraphAnalyzer()

    async def validate(self, kg_builder: KGBuilder) -> GraphHealthReport:
        subgraph = await self.analyzer.analyze_connectivity(kg_builder)
        isolated_nodes = await self.analyzer.find_isolated_nodes(kg_builder)
        suggestions: list[tuple[str, str, str]] = []
        if not subgraph.is_connected:
            suggestions = await self.analyzer.suggest_bridges(kg_builder)
        return GraphHealthReport(
            subgraph=subgraph,
            isolated_nodes=isolated_nodes,
            bridge_suggestions=suggestions,
        )

    async def fix_issues(self, kg_builder: KGBuilder, auto_fix: bool = False) -> int:
        if not auto_fix:
            return 0
        storage = await _resolve_storage(kg_builder)
        if storage is None:
            return 0
        suggestions = await self.analyzer.suggest_bridges(kg_builder)
        if not suggestions:
            return 0

        fixed = 0
        for source, relation_type, target in suggestions:
            try:
                applied = await self._apply_bridge(storage, source, relation_type, target)
            except Exception as exc:  # pragma: no cover - depends on backend implementation
                logger.warning(
                    "Failed to apply suggested bridge",
                    source=source,
                    target=target,
                    error=str(exc),
                )
                continue
            if applied:
                fixed += 1
        return fixed

    async def _apply_bridge(
        self, storage, source_name: str, relation_type: str, target_name: str
    ) -> bool:
        if NetworkXStorage and isinstance(storage, NetworkXStorage):
            return await self._apply_bridge_networkx(
                storage,
                source_name,
                relation_type,
                target_name,
            )
        if Neo4JStorage and isinstance(storage, Neo4JStorage):  # pragma: no cover - requires Neo4j
            return await self._apply_bridge_neo4j(
                storage,
                source_name,
                relation_type,
                target_name,
            )
        if hasattr(storage, "_get_graph"):
            return await self._apply_bridge_networkx(
                storage,
                source_name,
                relation_type,
                target_name,
            )
        if hasattr(storage, "_driver") and hasattr(storage, "_get_workspace_label"):
            return await self._apply_bridge_neo4j(
                storage,
                source_name,
                relation_type,
                target_name,
            )
        logger.warning("Unsupported storage backend for auto-fix", backend=type(storage).__name__)
        return False

    async def _apply_bridge_networkx(
        self, storage, source_name: str, relation_type: str, target_name: str
    ) -> bool:
        graph = await storage._get_graph()
        source_node = self._find_node_by_name(graph, source_name)
        target_node = self._find_node_by_name(graph, target_name)
        if source_node is None or target_node is None:
            logger.info(
                "Unable to create bridge; node missing",
                source=source_name,
                target=target_name,
            )
            return False
        graph.add_edge(
            source_node,
            target_node,
            relation_type=relation_type,
            confidence=1.0,
            provenance="auto-bridge",
        )
        return True

    async def _apply_bridge_neo4j(
        self, storage, source_name: str, relation_type: str, target_name: str
    ) -> bool:
        if getattr(storage, "_driver", None) is None:
            await storage.initialize()
        driver = getattr(storage, "_driver", None)
        if driver is None:
            return False
        label = storage._get_workspace_label()
        database = getattr(storage, "_DATABASE", None)
        cypher = f"""
        MATCH (source:`{label}` {{name: $source_name}}),
              (target:`{label}` {{name: $target_name}})
        MERGE (source)-[rel:DIRECTED {{relation_type: $relation_type}}]->(target)
        ON CREATE SET rel.confidence = $confidence,
                      rel.provenance = 'auto-bridge'
        RETURN 1 AS created
        """
        async with driver.session(database=database, default_access_mode="WRITE") as session:
            result = await session.run(
                cypher,
                source_name=source_name,
                target_name=target_name,
                relation_type=relation_type,
                confidence=1.0,
            )
            record = await result.single()
            return bool(record)

    @staticmethod
    def _find_node_by_name(graph, entity_name: str):
        for node_id, data in graph.nodes(data=True):
            node_name = data.get("name") or data.get("entity_name") or str(node_id)
            if node_name == entity_name:
                return node_id
        return None
