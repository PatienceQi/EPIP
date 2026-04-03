"""Knowledge graph quality evaluation and reporting utilities."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml

if TYPE_CHECKING:
    from epip.core.kg_builder import KGBuilder

logger = structlog.get_logger()

try:  # Optional at runtime depending on LightRAG configuration
    from lightrag.kg.neo4j_impl import Neo4JStorage
except Exception:  # pragma: no cover - Neo4j is optional in tests
    Neo4JStorage = None  # type: ignore

try:
    from lightrag.kg.networkx_impl import NetworkXStorage
except Exception:  # pragma: no cover - NetworkX backend may be absent
    NetworkXStorage = None  # type: ignore


@dataclass(slots=True)
class QualityThresholds:
    """Configurable thresholds for each quality dimension."""

    entity_precision: float = 0.8
    entity_recall: float = 0.75
    relation_coverage: float = 0.7
    graph_density: float = 0.01
    min_avg_degree: float = 1.0
    max_isolated_ratio: float = 0.1

    @classmethod
    def from_file(cls, path: Path) -> QualityThresholds:
        """Build thresholds from a YAML or JSON mapping."""
        data = _load_mapping(path)
        if not data:
            return cls()
        return cls.from_mapping(data)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> QualityThresholds:
        defaults = cls()
        return cls(
            entity_precision=float(data.get("entity_precision", defaults.entity_precision)),
            entity_recall=float(data.get("entity_recall", defaults.entity_recall)),
            relation_coverage=float(data.get("relation_coverage", defaults.relation_coverage)),
            graph_density=float(data.get("graph_density", defaults.graph_density)),
            min_avg_degree=float(data.get("min_avg_degree", defaults.min_avg_degree)),
            max_isolated_ratio=float(data.get("max_isolated_ratio", defaults.max_isolated_ratio)),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "entity_precision": self.entity_precision,
            "entity_recall": self.entity_recall,
            "relation_coverage": self.relation_coverage,
            "graph_density": self.graph_density,
            "min_avg_degree": self.min_avg_degree,
            "max_isolated_ratio": self.max_isolated_ratio,
        }


@dataclass(slots=True)
class EntityQualityMetrics:
    """Per-entity aggregation metrics."""

    precision: float
    recall: float
    f1: float
    missing_entities: list[str]


@dataclass(slots=True)
class RelationQualityMetrics:
    """Coverage metrics for required relations."""

    coverage: float
    missing_relations: list[str]


@dataclass(slots=True)
class GraphQualityMetrics:
    """Structural metrics describing the KG topology."""

    node_count: int
    edge_count: int
    component_count: int
    isolated_ratio: float
    density: float
    avg_degree: float


@dataclass(slots=True)
class KGQualityReport:
    """Combined summary across entity, relation, and graph metrics."""

    entity_metrics: EntityQualityMetrics
    relation_metrics: RelationQualityMetrics
    graph_metrics: GraphQualityMetrics
    overall_score: float
    passed: bool
    issues: list[str]
    score_breakdown: dict[str, float]


@dataclass(slots=True)
class _GroundTruth:
    """Internal container storing expected entities and relations."""

    entities: set[str]
    relations: set[tuple[str, str, str]]


@dataclass(slots=True)
class _GraphSnapshot:
    """Representation of the knowledge graph nodes and edges."""

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


class KGQualityEvaluator:
    """Evaluate the quality of LightRAG knowledge graphs."""

    def __init__(
        self,
        *,
        ground_truth_path: Path,
        thresholds: QualityThresholds | None = None,
    ) -> None:
        self.ground_truth_path = Path(ground_truth_path)
        self.thresholds = thresholds or QualityThresholds()
        self._ground_truth = self._load_ground_truth()

    async def evaluate_entities(self, kg_builder: KGBuilder) -> EntityQualityMetrics:
        snapshot = await _get_graph_snapshot(kg_builder)
        return self._evaluate_entities(snapshot)

    async def evaluate_relations(self, kg_builder: KGBuilder) -> RelationQualityMetrics:
        snapshot = await _get_graph_snapshot(kg_builder)
        return self._evaluate_relations(snapshot)

    async def evaluate_graph(self, kg_builder: KGBuilder) -> GraphQualityMetrics:
        snapshot = await _get_graph_snapshot(kg_builder)
        return self._evaluate_graph(snapshot)

    async def generate_report(self, kg_builder: KGBuilder) -> KGQualityReport:
        snapshot = await _get_graph_snapshot(kg_builder)
        entity_metrics = self._evaluate_entities(snapshot)
        relation_metrics = self._evaluate_relations(snapshot)
        graph_metrics = self._evaluate_graph(snapshot)
        score_breakdown = self._score_breakdown(
            entity_metrics,
            relation_metrics,
            graph_metrics,
        )
        overall_score = self._overall_score(score_breakdown)
        issues = self._collect_issues(entity_metrics, relation_metrics, graph_metrics)
        passed = not issues
        return KGQualityReport(
            entity_metrics=entity_metrics,
            relation_metrics=relation_metrics,
            graph_metrics=graph_metrics,
            overall_score=overall_score,
            passed=passed,
            issues=issues,
            score_breakdown=score_breakdown,
        )

    def export_markdown(self, report: KGQualityReport, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Knowledge Graph Quality Report", ""]
        lines.append("## Summary")
        lines.append(f"- Overall score: {report.overall_score:.2f}")
        lines.append(f"- Status: {'PASSED' if report.passed else 'FAILED'}")
        lines.append("")
        lines.append("## Score Breakdown")
        for name, score in report.score_breakdown.items():
            lines.append(f"- {name}: {score * 100:.1f}%")
        lines.append("")
        lines.append("## Entity Metrics")
        entity = report.entity_metrics
        lines.append(f"- Precision: {entity.precision:.2%}")
        lines.append(f"- Recall: {entity.recall:.2%}")
        lines.append(f"- F1 Score: {entity.f1:.2%}")
        if entity.missing_entities:
            lines.append("- Missing entities:")
            for missing in entity.missing_entities:
                lines.append(f"  - {missing}")
        else:
            lines.append("- Missing entities: none")
        lines.append("")
        lines.append("## Relation Metrics")
        relation = report.relation_metrics
        lines.append(f"- Coverage: {relation.coverage:.2%}")
        if relation.missing_relations:
            lines.append("- Missing relations:")
            for rel in relation.missing_relations:
                lines.append(f"  - {rel}")
        else:
            lines.append("- Missing relations: none")
        lines.append("")
        lines.append("## Graph Metrics")
        graph = report.graph_metrics
        lines.append(f"- Nodes: {graph.node_count}")
        lines.append(f"- Edges: {graph.edge_count}")
        lines.append(f"- Components: {graph.component_count}")
        lines.append(f"- Isolated ratio: {graph.isolated_ratio:.2%}")
        lines.append(f"- Density: {graph.density:.4f}")
        lines.append(f"- Average degree: {graph.avg_degree:.2f}")
        lines.append("")
        if report.issues:
            lines.append("## Issues")
            for issue in report.issues:
                lines.append(f"- {issue}")
        else:
            lines.append("## Issues")
            lines.append("- None detected")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("KG quality markdown exported", path=str(output_path))
        return output_path

    def export_json(self, report: KGQualityReport, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(report)
        payload["ground_truth_path"] = str(self.ground_truth_path)
        payload["thresholds"] = self.thresholds.to_dict()
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("KG quality JSON exported", path=str(output_path))
        return output_path

    def _evaluate_entities(self, snapshot: _GraphSnapshot) -> EntityQualityMetrics:
        actual_entities = {snapshot.node_name(node_id).strip() for node_id in snapshot.nodes}
        actual_entities.discard("")
        expected_entities = self._ground_truth.entities
        true_positive = len(actual_entities & expected_entities)
        actual_total = len(actual_entities)
        expected_total = len(expected_entities)
        precision = self._safe_div(
            true_positive,
            actual_total,
            empty_value=1.0 if expected_total == 0 else 0.0,
        )
        recall = self._safe_div(true_positive, expected_total, empty_value=1.0)
        if precision + recall == 0:
            f1_score = 0.0
        else:
            f1_score = 2 * (precision * recall) / (precision + recall)
        missing_entities = sorted(expected_entities - actual_entities)
        return EntityQualityMetrics(
            precision=precision,
            recall=recall,
            f1=f1_score,
            missing_entities=missing_entities,
        )

    def _evaluate_relations(self, snapshot: _GraphSnapshot) -> RelationQualityMetrics:
        actual_relations = {
            (
                snapshot.node_name(source).strip(),
                edge_payload.get("relation_type") or "RELATED_TO",
                snapshot.node_name(target).strip(),
            )
            for source, target, edge_payload in snapshot.edges
        }
        clean_actual = {rel for rel in actual_relations if rel[0] and rel[2]}
        expected = self._ground_truth.relations
        matching = len(clean_actual & expected)
        expected_total = len(expected)
        coverage = self._safe_div(matching, expected_total, empty_value=1.0)
        missing_relations = [
            _format_relation(relation) for relation in sorted(expected - clean_actual)
        ]
        return RelationQualityMetrics(
            coverage=coverage,
            missing_relations=missing_relations,
        )

    def _evaluate_graph(self, snapshot: _GraphSnapshot) -> GraphQualityMetrics:
        adjacency = snapshot.adjacency()
        node_count = len(adjacency)
        edge_count = len(snapshot.edges)
        components = _connected_components(adjacency)
        component_count = len(components)
        isolated = [
            snapshot.node_name(node_id) for node_id, neighbors in adjacency.items() if not neighbors
        ]
        isolated_ratio = self._safe_div(len(isolated), node_count, empty_value=0.0)
        density = self._graph_density(node_count, edge_count)
        avg_degree = 2 * edge_count / node_count if node_count > 0 else 0.0
        return GraphQualityMetrics(
            node_count=node_count,
            edge_count=edge_count,
            component_count=component_count,
            isolated_ratio=isolated_ratio,
            density=density,
            avg_degree=avg_degree,
        )

    def _score_breakdown(
        self,
        entity_metrics: EntityQualityMetrics,
        relation_metrics: RelationQualityMetrics,
        graph_metrics: GraphQualityMetrics,
    ) -> dict[str, float]:
        thresholds = self.thresholds
        entity_precision_score = self._normalize(
            entity_metrics.precision,
            thresholds.entity_precision,
        )
        entity_recall_score = self._normalize(
            entity_metrics.recall,
            thresholds.entity_recall,
        )
        entity_score = min((entity_precision_score + entity_recall_score) / 2, 1.0)
        relation_score = self._normalize(
            relation_metrics.coverage,
            thresholds.relation_coverage,
        )
        density_score = self._normalize(graph_metrics.density, thresholds.graph_density)
        avg_degree_score = self._normalize(graph_metrics.avg_degree, thresholds.min_avg_degree)
        isolated_score = self._normalize_inverse(
            graph_metrics.isolated_ratio,
            thresholds.max_isolated_ratio,
        )
        graph_score = (density_score + avg_degree_score + isolated_score) / 3
        return {
            "Entities": max(0.0, min(entity_score, 1.0)),
            "Relations": max(0.0, min(relation_score, 1.0)),
            "Graph": max(0.0, min(graph_score, 1.0)),
        }

    def _overall_score(self, scores: Mapping[str, float]) -> float:
        if not scores:
            return 0.0
        total = sum(scores.values())
        return round((total / len(scores)) * 100, 2)

    def _collect_issues(
        self,
        entity_metrics: EntityQualityMetrics,
        relation_metrics: RelationQualityMetrics,
        graph_metrics: GraphQualityMetrics,
    ) -> list[str]:
        thresholds = self.thresholds
        issues: list[str] = []
        if entity_metrics.precision < thresholds.entity_precision:
            issues.append(
                f"Entity precision {entity_metrics.precision:.2f} below "
                f"{thresholds.entity_precision:.2f}"
            )
        if entity_metrics.recall < thresholds.entity_recall:
            issues.append(
                f"Entity recall {entity_metrics.recall:.2f} below {thresholds.entity_recall:.2f}"
            )
        if relation_metrics.coverage < thresholds.relation_coverage:
            issues.append(
                f"Relation coverage {relation_metrics.coverage:.2f} below "
                f"{thresholds.relation_coverage:.2f}"
            )
        if graph_metrics.density < thresholds.graph_density:
            issues.append(
                f"Graph density {graph_metrics.density:.4f} below {thresholds.graph_density:.4f}"
            )
        if graph_metrics.avg_degree < thresholds.min_avg_degree:
            issues.append(
                f"Average degree {graph_metrics.avg_degree:.2f} below "
                f"{thresholds.min_avg_degree:.2f}"
            )
        if graph_metrics.isolated_ratio > thresholds.max_isolated_ratio:
            issues.append(
                f"Isolated node ratio {graph_metrics.isolated_ratio:.2f} above "
                f"{thresholds.max_isolated_ratio:.2f}"
            )
        return issues

    def _load_ground_truth(self) -> _GroundTruth:
        if not self.ground_truth_path.exists():
            logger.warning(
                "Ground truth file missing; proceeding without expectations",
                path=str(self.ground_truth_path),
            )
            return _GroundTruth(entities=set(), relations=set())
        data = _load_mapping(self.ground_truth_path)
        if not isinstance(data, Mapping):
            return _GroundTruth(entities=set(), relations=set())
        entities = {
            str(item.get("name", "")).strip()
            for item in data.get("entities", [])
            if isinstance(item, Mapping) and str(item.get("name", "")).strip()
        }
        relations: set[tuple[str, str, str]] = set()
        for item in data.get("relations", []):
            if not isinstance(item, Mapping):
                continue
            source = str(item.get("source", "")).strip()
            target = str(item.get("target", "")).strip()
            relation_type = str(
                item.get("relation_type") or item.get("type") or "RELATED_TO"
            ).strip()
            if source and target:
                relations.add((source, relation_type, target))
        return _GroundTruth(entities=entities, relations=relations)

    @staticmethod
    def _safe_div(numerator: float, denominator: float, *, empty_value: float) -> float:
        if denominator == 0:
            return float(empty_value)
        return float(numerator) / float(denominator)

    @staticmethod
    def _normalize(value: float, threshold: float) -> float:
        if threshold <= 0:
            return 1.0 if value > 0 else 0.0
        return max(0.0, min(value / threshold, 1.0))

    @staticmethod
    def _normalize_inverse(value: float, threshold: float) -> float:
        if threshold <= 0:
            return 1.0 if value == 0 else 0.0
        if value <= threshold:
            return 1.0
        if value == 0:
            return 1.0
        return max(0.0, min(threshold / value, 1.0))

    @staticmethod
    def _graph_density(node_count: int, edge_count: int) -> float:
        if node_count < 2:
            return 0.0
        max_edges = node_count * (node_count - 1)
        if max_edges == 0:
            return 0.0
        return edge_count / max_edges


class QualityReportGenerator:
    """Utility helpers for presenting KG quality results."""

    def generate_ascii_chart(
        self,
        scores: Mapping[str, float],
        width: int = 30,
    ) -> str:
        if not scores:
            return "(no scores)"
        lines: list[str] = []
        for label, value in scores.items():
            normalized = max(0.0, min(float(value), 1.0))
            filled = int(round(normalized * width))
            filled = min(filled, width)
            bar = "#" * filled + "-" * (width - filled)
            lines.append(f"{label:>10}: [{bar}] {normalized * 100:5.1f}%")
        return "\n".join(lines)


async def _get_graph_snapshot(kg_builder: KGBuilder) -> _GraphSnapshot:
    storage = await _resolve_storage(kg_builder)
    if storage is None:
        return _GraphSnapshot(nodes={}, edges=[])
    if NetworkXStorage and isinstance(storage, NetworkXStorage):
        return await _snapshot_from_networkx(storage)
    if Neo4JStorage and isinstance(storage, Neo4JStorage):  # pragma: no cover - requires Neo4j
        return await _snapshot_from_neo4j(storage)
    if hasattr(storage, "_get_graph"):
        return await _snapshot_from_networkx(storage)
    if hasattr(storage, "_driver") and hasattr(storage, "_get_workspace_label"):
        return await _snapshot_from_neo4j(storage)
    logger.warning(
        "Unsupported storage backend for quality snapshot",
        backend=type(storage).__name__,
    )
    return _GraphSnapshot(nodes={}, edges=[])


async def _resolve_storage(kg_builder: KGBuilder) -> Any | None:
    require_rag = getattr(kg_builder, "_require_rag", None)
    ensure_initialized = getattr(kg_builder, "_ensure_initialized", None)
    if not callable(require_rag) or not callable(ensure_initialized):
        logger.warning("KGBuilder is not ready; storage unavailable for quality evaluation")
        return None
    rag = require_rag()
    await ensure_initialized()
    return getattr(rag, "chunk_entity_relation_graph", None)


async def _snapshot_from_networkx(storage) -> _GraphSnapshot:
    graph = await storage._get_graph()
    nodes: dict[str, dict[str, Any]] = {}
    for node_id, data in graph.nodes(data=True):
        node_key = str(node_id)
        payload = dict(data)
        payload.setdefault("name", data.get("entity_name") or node_key)
        nodes[node_key] = payload
    edges: list[tuple[str, str, dict[str, Any]]] = []
    for source, target, attributes in graph.edges(data=True):
        edges.append(
            (
                str(source),
                str(target),
                {
                    "relation_type": attributes.get("relation_type")
                    or attributes.get("type")
                    or "RELATED_TO",
                    "confidence": float(attributes.get("confidence") or 0.0),
                },
            )
        )
    return _GraphSnapshot(nodes=nodes, edges=edges)


async def _snapshot_from_neo4j(storage) -> _GraphSnapshot:
    if getattr(storage, "_driver", None) is None:
        await storage.initialize()
    driver = getattr(storage, "_driver", None)
    if driver is None:
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


def _connected_components(adjacency: Mapping[str, Iterable[str]]) -> list[set[str]]:
    visited: set[str] = set()
    components: list[set[str]] = []
    for node in adjacency:
        if node in visited:
            continue
        stack = [node]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            neighbors = adjacency.get(current, [])
            for neighbor in neighbors:
                if neighbor not in visited:
                    stack.append(neighbor)
        components.append(component)
    return components


def _format_relation(relation: tuple[str, str, str]) -> str:
    source, relation_type, target = relation
    return f"{source} --{relation_type}--> {target}"


def _load_mapping(path: Path) -> Mapping[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Threshold/ground truth file not found", path=str(path))
        return {}
    except Exception as exc:  # pragma: no cover - filesystem errors are environment specific
        logger.warning("Failed to read configuration file", path=str(path), error=str(exc))
        return {}
    if not content.strip():
        return {}
    try:
        if path.suffix.lower() in {".json"}:
            return json.loads(content)
        return yaml.safe_load(content) or {}
    except Exception as exc:  # pragma: no cover - depends on file contents
        logger.warning("Failed to parse configuration file", path=str(path), error=str(exc))
        return {}
