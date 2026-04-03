"""Entity extraction utilities for LightRAG knowledge graphs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog

if TYPE_CHECKING:
    from epip.core.kg_builder import KGBuilder

logger = structlog.get_logger()

try:  # Optional dependencies resolved via LightRAG extras
    from lightrag.kg.neo4j_impl import Neo4JStorage
except Exception:  # pragma: no cover - optional backend
    Neo4JStorage = None  # type: ignore

try:
    from lightrag.kg.networkx_impl import NetworkXStorage
except Exception:  # pragma: no cover - optional backend
    NetworkXStorage = None  # type: ignore


@dataclass(slots=True)
class EntityExtractionConfig:
    """Configuration controlling entity extraction and disambiguation."""

    confidence_threshold: float = 0.6
    entity_types: list[str] = field(
        default_factory=lambda: [
            "POLICY",
            "ORGANIZATION",
            "PERSON",
            "LOCATION",
            "DATE",
            "METRIC",
            "DISEASE",
            "BUDGET",
        ]
    )
    max_entities_per_chunk: int = 50
    enable_disambiguation: bool = True
    similarity_threshold: float = 0.85
    report_sample_size: int = 20


class EntityDisambiguator:
    """Resolve duplicate entities based on embedding similarity."""

    def __init__(
        self,
        *,
        similarity_threshold: float = 0.85,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.threshold = similarity_threshold
        self.model_name = model_name
        self._embedding_model = None

    async def _embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(self.model_name)
        return await asyncio.to_thread(
            self._embedding_model.encode,
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    @staticmethod
    def _cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
        norm_a = np.linalg.norm(vector_a)
        norm_b = np.linalg.norm(vector_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vector_a, vector_b) / (norm_a * norm_b))

    async def find_similar_entities(
        self, entity_name: str, candidates: Sequence[str]
    ) -> list[tuple[str, float]]:
        """Return candidate entities sorted by similarity score."""

        if not entity_name or not candidates:
            return []

        embeddings = await self._embed_texts([entity_name, *candidates])
        base_vector = embeddings[0]
        candidate_vectors = embeddings[1:]

        scored: list[tuple[str, float]] = []
        for candidate, vector in zip(candidates, candidate_vectors):
            score = self._cosine_similarity(base_vector, vector)
            if score >= self.threshold:
                scored.append((candidate, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    async def merge_entities(
        self, kg_builder: KGBuilder, entity_pairs: Sequence[tuple[str, str]]
    ) -> int:
        """Merge duplicate entities in the configured storage backend."""

        if not entity_pairs:
            return 0

        require_rag = getattr(kg_builder, "_require_rag", None)
        ensure_initialized = getattr(kg_builder, "_ensure_initialized", None)
        if not callable(require_rag) or not callable(ensure_initialized):
            logger.warning("KGBuilder not initialized; skipping entity merge.")
            return 0

        rag = require_rag()
        await ensure_initialized()
        storage = getattr(rag, "chunk_entity_relation_graph", None)
        if storage is None:
            logger.warning("LightRAG storage missing; unable to merge entities.")
            return 0

        if Neo4JStorage and isinstance(storage, Neo4JStorage):
            return await self._merge_in_neo4j(storage, entity_pairs)
        if NetworkXStorage and isinstance(storage, NetworkXStorage):
            return await self._merge_in_networkx(storage, entity_pairs)

        logger.warning("Unsupported storage backend for merging", backend=type(storage).__name__)
        return 0

    async def _merge_in_neo4j(self, storage, entity_pairs: Sequence[tuple[str, str]]) -> int:
        if getattr(storage, "_driver", None) is None:
            await storage.initialize()
        driver = storage._driver
        if driver is None:
            logger.warning("Neo4j driver unavailable; cannot merge entities.")
            return 0
        label = storage._get_workspace_label()
        database = getattr(storage, "_DATABASE", None)

        merged = 0
        async with driver.session(database=database, default_access_mode="WRITE") as session:
            for alias_name, target_name in entity_pairs:
                if alias_name == target_name:
                    continue
                cypher = f"""
                MATCH (alias:`{label}` {{name: $alias_name}}),
                      (target:`{label}` {{name: $target_name}})
                OPTIONAL MATCH (alias)-[out_rel:DIRECTED]->(neighbor)
                FOREACH (_ IN CASE WHEN out_rel IS NULL THEN [] ELSE [1] END |
                    MERGE (target)-[new_out:DIRECTED]->(neighbor)
                    SET new_out += properties(out_rel)
                    DELETE out_rel
                )
                OPTIONAL MATCH (neighbor)-[in_rel:DIRECTED]->(alias)
                FOREACH (_ IN CASE WHEN in_rel IS NULL THEN [] ELSE [1] END |
                    MERGE (neighbor)-[new_in:DIRECTED]->(target)
                    SET new_in += properties(in_rel)
                    DELETE in_rel
                )
                SET target.confidence = CASE
                    WHEN target.confidence IS NULL THEN alias.confidence
                    WHEN alias.confidence IS NULL THEN target.confidence
                    WHEN target.confidence >= alias.confidence THEN target.confidence
                    ELSE alias.confidence
                END,
                target.aliases = CASE
                    WHEN target.aliases IS NULL THEN [$alias_name]
                    WHEN NOT $alias_name IN target.aliases THEN target.aliases + $alias_name
                    ELSE target.aliases
                END
                DETACH DELETE alias
                RETURN 1 AS merged
                """
                try:
                    result = await session.run(
                        cypher,
                        alias_name=alias_name,
                        target_name=target_name,
                    )
                    record = await result.single()
                except Exception as exc:  # pragma: no cover - depends on Neo4j at runtime
                    logger.warning(
                        "Failed to merge Neo4j entities",
                        alias=alias_name,
                        target=target_name,
                        error=str(exc),
                    )
                    continue
                if record:
                    merged += int(record["merged"]) if "merged" in record else 0
        return merged

    async def _merge_in_networkx(self, storage, entity_pairs: Sequence[tuple[str, str]]) -> int:
        graph = await storage._get_graph()
        merged = 0
        for alias_name, target_name in entity_pairs:
            if alias_name == target_name:
                continue
            alias_node = self._find_node_by_name(graph, alias_name)
            target_node = self._find_node_by_name(graph, target_name)
            if alias_node is None or target_node is None:
                logger.info(
                    "Entity not found in graph during merge",
                    alias=alias_name,
                    target=target_name,
                )
                continue
            self._merge_networkx_nodes(graph, alias_node, target_node, alias_name)
            merged += 1
        return merged

    @staticmethod
    def _find_node_by_name(graph, entity_name: str):
        for node_id, data in graph.nodes(data=True):
            node_name = data.get("name") or data.get("entity_name")
            if node_name == entity_name:
                return node_id
        return None

    @staticmethod
    def _merge_networkx_nodes(graph, alias_node, target_node, alias_name: str) -> None:
        alias_data = graph.nodes[alias_node]
        target_data = graph.nodes[target_node]
        aliases = target_data.setdefault("aliases", [])
        if alias_name not in aliases:
            aliases.append(alias_name)
        target_data["confidence"] = max(
            float(target_data.get("confidence") or 0.0),
            float(alias_data.get("confidence") or 0.0),
        )

        is_directed = graph.is_directed()
        if is_directed:
            outgoing = graph.out_edges(alias_node, data=True)
            incoming = graph.in_edges(alias_node, data=True)
        else:
            outgoing = graph.edges(alias_node, data=True)
            incoming = []

        for _, neighbor, attributes in list(outgoing):
            graph.add_edge(target_node, neighbor, **dict(attributes))
        for neighbor, _, attributes in list(incoming):
            graph.add_edge(neighbor, target_node, **dict(attributes))
        graph.remove_node(alias_node)


@dataclass(slots=True)
class EntityReport:
    """Aggregated entity statistics."""

    total_entities: int
    entity_type_counts: dict[str, int]
    low_confidence_count: int
    disambiguation_count: int
    sample_entities: list[dict[str, Any]]


class EntityReportGenerator:
    """Generate entity recognition reports from the KG."""

    def __init__(self, config: EntityExtractionConfig | None = None) -> None:
        self.config = config or EntityExtractionConfig()

    async def generate_report(self, kg_builder: KGBuilder) -> EntityReport:
        stats = await kg_builder.get_statistics()
        (
            sample_entities,
            low_confidence_count,
            disambiguation_count,
        ) = await self._collect_entity_samples(
            kg_builder, limit=max(self.config.report_sample_size, 0)
        )
        return EntityReport(
            total_entities=stats.total_entities,
            entity_type_counts=stats.entity_types,
            low_confidence_count=low_confidence_count,
            disambiguation_count=disambiguation_count,
            sample_entities=sample_entities,
        )

    async def _collect_entity_samples(
        self, kg_builder: KGBuilder, *, limit: int
    ) -> tuple[list[dict[str, Any]], int, int]:
        require_rag = getattr(kg_builder, "_require_rag", None)
        ensure_initialized = getattr(kg_builder, "_ensure_initialized", None)
        if not callable(require_rag) or not callable(ensure_initialized):
            return [], 0, 0
        rag = require_rag()
        await ensure_initialized()
        storage = getattr(rag, "chunk_entity_relation_graph", None)
        if storage is None:
            return [], 0, 0
        if Neo4JStorage and isinstance(storage, Neo4JStorage):
            return await self._collect_from_neo4j(storage, limit)
        if NetworkXStorage and isinstance(storage, NetworkXStorage):
            return await self._collect_from_networkx(storage, limit)
        return [], 0, 0

    async def _collect_from_neo4j(
        self, storage, limit: int
    ) -> tuple[list[dict[str, Any]], int, int]:
        if getattr(storage, "_driver", None) is None:
            await storage.initialize()
        driver = storage._driver
        if driver is None:
            return [], 0, 0
        label = storage._get_workspace_label()
        database = getattr(storage, "_DATABASE", None)
        sample: list[dict[str, Any]] = []

        async with driver.session(database=database, default_access_mode="READ") as session:
            query = f"""
            MATCH (n:`{label}`)
            RETURN n.name AS name,
                   coalesce(n.entity_type, n.type, 'UNKNOWN') AS entity_type,
                   coalesce(n.confidence, 0.0) AS confidence,
                   coalesce(n.aliases, []) AS aliases,
                   coalesce(n.metadata, {{}}) AS metadata
            ORDER BY confidence DESC
            LIMIT $limit
            """
            result = await session.run(query, limit=limit)
            async for row in result:
                sample.append(
                    {
                        "name": row["name"],
                        "type": row["entity_type"],
                        "confidence": float(row["confidence"]),
                        "aliases": row["aliases"],
                        "metadata": row["metadata"],
                    }
                )
            low_conf_query = f"""
            MATCH (n:`{label}`)
            WHERE coalesce(n.confidence, 0.0) < $threshold
            RETURN count(n) AS total
            """
            low_conf_result = await session.run(
                low_conf_query, threshold=self.config.confidence_threshold
            )
            low_conf_record = await low_conf_result.single()
            low_confidence = low_conf_record["total"] if low_conf_record else 0

            disambiguation_query = f"""
            MATCH (n:`{label}`)
            WHERE size(coalesce(n.aliases, [])) > 0
            RETURN count(n) AS total
            """
            disambiguation_result = await session.run(disambiguation_query)
            disambiguation_record = await disambiguation_result.single()
            disambiguation_count = disambiguation_record["total"] if disambiguation_record else 0

        return sample, low_confidence, disambiguation_count

    async def _collect_from_networkx(
        self, storage, limit: int
    ) -> tuple[list[dict[str, Any]], int, int]:
        graph = await storage._get_graph()
        nodes = list(graph.nodes(data=True))
        nodes.sort(key=lambda item: item[1].get("confidence", 0), reverse=True)
        low_confidence = 0
        disambiguation_count = 0
        for _, data in nodes:
            confidence = float(data.get("confidence") or 0.0)
            if confidence < self.config.confidence_threshold:
                low_confidence += 1
            aliases = data.get("aliases") or []
            if aliases:
                disambiguation_count += 1
        sample: list[dict[str, Any]] = []
        take = len(nodes) if limit <= 0 else min(limit, len(nodes))
        for node_id, data in nodes[:take]:
            sample.append(
                {
                    "name": data.get("name") or str(node_id),
                    "type": data.get("entity_type") or data.get("type") or "UNKNOWN",
                    "confidence": float(data.get("confidence") or 0.0),
                    "aliases": data.get("aliases", []),
                    "metadata": data.get("metadata", {}),
                }
            )
        return sample, low_confidence, disambiguation_count

    def export_markdown(self, report: EntityReport, output_path: Path) -> Path:
        """Persist the report to a Markdown file."""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Entity Recognition Report", ""]
        lines.append(f"Total entities: {report.total_entities}")
        lines.append(
            f"Low confidence entities (<{self.config.confidence_threshold}): "
            f"{report.low_confidence_count}"
        )
        lines.append(f"Entities with aliases: {report.disambiguation_count}")
        lines.append("")
        lines.append("## Entity Types")
        for entity_type, count in sorted(report.entity_type_counts.items()):
            lines.append(f"- {entity_type}: {count}")
        lines.append("")
        lines.append("## Sample Entities")
        for entity in report.sample_entities:
            alias_text = ", ".join(entity.get("aliases", [])) or "None"
            lines.append(
                f"- **{entity['name']}** ({entity['type']}), "
                f"confidence={entity['confidence']:.2f}, aliases={alias_text}"
            )
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Entity report exported", path=str(output_path))
        return output_path


@dataclass(slots=True)
class EvaluationResult:
    """Precision/recall evaluation for entity extraction."""

    precision: float
    recall: float
    f1_score: float
    confusion_matrix: dict[str, dict[str, int]]


class EntityEvaluator:
    """Compare extracted entities with labeled ground truth."""

    def __init__(self, ground_truth_path: Path) -> None:
        self.ground_truth_path = ground_truth_path
        self.ground_truth = self._load_ground_truth(ground_truth_path)

    def _load_ground_truth(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            logger.warning("Ground truth file missing", path=str(path))
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("Invalid ground truth JSON", error=str(exc))
            return []

    def evaluate(
        self,
        extracted: Sequence[dict[str, Any]],
        ground_truth: Sequence[dict[str, Any]] | None = None,
    ) -> EvaluationResult:
        truth = ground_truth or self.ground_truth
        ground_truth_set: set[tuple[str, str]] = set()
        for entity in truth:
            normalized = self._normalize_entity(entity)
            if normalized:
                ground_truth_set.add(normalized)

        extracted_set: set[tuple[str, str]] = set()
        for entity in extracted:
            normalized = self._normalize_entity(entity)
            if normalized:
                extracted_set.add(normalized)

        true_positives = len(ground_truth_set & extracted_set)
        precision = true_positives / len(extracted_set) if extracted_set else 0.0
        recall = true_positives / len(ground_truth_set) if ground_truth_set else 0.0
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        confusion = self._build_confusion_matrix(extracted, truth)
        return EvaluationResult(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            confusion_matrix=confusion,
        )

    @staticmethod
    def _normalize_entity(entity: dict[str, Any]) -> tuple[str, str] | None:
        name = entity.get("name") or entity.get("entity_name")
        entity_type = entity.get("type") or entity.get("entity_type")
        if not name:
            return None
        normalized_name = name.strip().lower()
        normalized_type = (entity_type or "UNKNOWN").strip().upper()
        return normalized_name, normalized_type

    def _build_confusion_matrix(
        self, extracted: Sequence[dict[str, Any]], truth: Sequence[dict[str, Any]]
    ) -> dict[str, dict[str, int]]:
        by_name: dict[str, str] = {}
        for entity in truth:
            normalized = self._normalize_entity(entity)
            if normalized is None:
                continue
            name, entity_type = normalized
            by_name[name] = entity_type

        confusion: dict[str, dict[str, int]] = {}
        for entity in extracted:
            predicted_type = (
                (entity.get("type") or entity.get("entity_type") or "UNKNOWN").strip().upper()
            )
            normalized = self._normalize_entity(entity)
            name = normalized[0] if normalized else None
            actual_type = by_name.get(name, "UNKNOWN")
            row = confusion.setdefault(actual_type, {})
            row[predicted_type] = row.get(predicted_type, 0) + 1
        return confusion
