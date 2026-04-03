"""Entity linking utilities for the query parsing pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import structlog

from epip.query.parser import EntityMention

if TYPE_CHECKING:
    from epip.core.kg_builder import KGBuilder

logger = structlog.get_logger(__name__)

try:  # Optional imports resolved at runtime
    from lightrag.kg.neo4j_impl import Neo4JStorage
except Exception:  # pragma: no cover - optional dependency
    Neo4JStorage = None  # type: ignore

try:
    from lightrag.kg.networkx_impl import NetworkXStorage
except Exception:  # pragma: no cover - optional dependency
    NetworkXStorage = None  # type: ignore


@dataclass(slots=True)
class LinkedEntity:
    """Entity mention mapped to a candidate KG node."""

    mention: EntityMention
    kg_node_id: str
    kg_node_name: str
    confidence: float
    alternatives: list[tuple[str, float]] = field(default_factory=list)


class EntityLinker:
    """Entity linker that relies on embedding similarity for fuzzy matching."""

    def __init__(
        self,
        *,
        similarity_threshold: float = 0.65,
        max_alternatives: int = 3,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        candidate_limit: int = 500,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.max_alternatives = max_alternatives
        self.embedding_model = embedding_model
        self.candidate_limit = candidate_limit
        self._embedding_model = None

    async def link(
        self,
        mentions: list[EntityMention],
        kg_builder: KGBuilder,
    ) -> list[LinkedEntity]:
        """Resolve query mentions to candidate KG nodes."""
        if not mentions:
            return []
        catalog = await self._load_entity_catalog(kg_builder)
        if not catalog:
            logger.debug("Entity catalog unavailable; skipping entity linking.")
            return []

        linked: list[LinkedEntity] = []
        for mention in mentions:
            candidates = self._filter_candidates(catalog, mention.entity_type)
            if not candidates:
                continue
            candidate_names = [candidate["name"] for candidate in candidates]
            matches = await self.fuzzy_match(
                mention.text,
                candidate_names,
                threshold=self.similarity_threshold,
            )
            if not matches:
                continue
            best_name, confidence = matches[0]
            record = next((item for item in candidates if item["name"] == best_name), None)
            node_id = str(record["id"]) if record else best_name
            node_name = record["name"] if record else best_name
            alternatives = [(name, score) for name, score in matches[1 : self.max_alternatives + 1]]
            linked.append(
                LinkedEntity(
                    mention=mention,
                    kg_node_id=node_id,
                    kg_node_name=node_name,
                    confidence=float(confidence),
                    alternatives=alternatives,
                )
            )
        return linked

    async def fuzzy_match(
        self,
        text: str,
        candidates: list[str],
        threshold: float = 0.7,
    ) -> list[tuple[str, float]]:
        """Rank candidate entity names by cosine similarity."""
        if not text or not candidates:
            return []
        embeddings = await self._embed_texts([text, *candidates])
        if embeddings.size == 0:
            return []
        base_vector = embeddings[0]
        candidate_vectors = embeddings[1:]
        scored: list[tuple[str, float]] = []
        for candidate, vector in zip(candidates, candidate_vectors):
            score = self._cosine_similarity(base_vector, vector)
            if score >= threshold:
                scored.append((candidate, float(score)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    def _filter_candidates(
        self,
        catalog: Sequence[dict[str, Any]],
        entity_type: str | None,
    ) -> list[dict[str, Any]]:
        if not entity_type:
            return list(catalog)
        filtered = [record for record in catalog if record.get("entity_type") == entity_type]
        return filtered or list(catalog)

    async def _load_entity_catalog(self, kg_builder: KGBuilder) -> list[dict[str, Any]]:
        if kg_builder is None:
            return []

        # Allow mocks that expose list_entities during tests.
        list_entities = getattr(kg_builder, "list_entities", None)
        if callable(list_entities):
            result = list_entities()
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, Sequence):
                catalog: list[dict[str, Any]] = []
                for entry in result[: self.candidate_limit]:
                    if isinstance(entry, dict):
                        raw_name = entry.get("name") or entry.get("entity_name")
                        entity_type = entry.get("entity_type")
                        identifier = entry.get("id") or raw_name
                    else:
                        raw_name = getattr(entry, "name", None) or getattr(
                            entry, "entity_name", None
                        )
                        entity_type = getattr(entry, "entity_type", None)
                        identifier = getattr(entry, "id", None) or raw_name
                    if not raw_name or not identifier:
                        continue
                    catalog.append(
                        {
                            "id": str(identifier),
                            "name": str(raw_name),
                            "entity_type": entity_type,
                        }
                    )
                if catalog:
                    return catalog

        storage = await self._resolve_storage(kg_builder)
        if storage is None:
            return []
        if NetworkXStorage and isinstance(storage, NetworkXStorage):
            return await self._catalog_from_networkx(storage)
        if Neo4JStorage and isinstance(storage, Neo4JStorage):
            return await self._catalog_from_neo4j(storage)

        if hasattr(storage, "_get_graph"):
            return await self._catalog_from_networkx(storage)
        if hasattr(storage, "_driver") and hasattr(storage, "_get_workspace_label"):
            return await self._catalog_from_neo4j(storage)

        logger.warning(
            "Unsupported storage backend for entity linking",
            backend=type(storage).__name__,
        )
        return []

    async def _resolve_storage(self, kg_builder: KGBuilder) -> Any | None:
        require_rag = getattr(kg_builder, "_require_rag", None)
        ensure_initialized = getattr(kg_builder, "_ensure_initialized", None)
        if not callable(require_rag) or not callable(ensure_initialized):
            return None
        rag = require_rag()
        await ensure_initialized()
        return getattr(rag, "chunk_entity_relation_graph", None)

    async def _catalog_from_networkx(self, storage) -> list[dict[str, Any]]:
        graph = await storage._get_graph()
        catalog: list[dict[str, Any]] = []
        for node_id, data in graph.nodes(data=True):
            name = data.get("name") or data.get("entity_name") or str(node_id)
            catalog.append(
                {
                    "id": str(node_id),
                    "name": str(name),
                    "entity_type": data.get("entity_type") or data.get("type"),
                }
            )
            if len(catalog) >= self.candidate_limit:
                break
        return catalog

    async def _catalog_from_neo4j(self, storage) -> list[dict[str, Any]]:
        if getattr(storage, "_driver", None) is None:
            await storage.initialize()
        driver = getattr(storage, "_driver", None)
        if driver is None:  # pragma: no cover - depends on Neo4j availability
            return []
        label = storage._get_workspace_label()
        database = getattr(storage, "_DATABASE", None)
        query = (
            f"MATCH (n:`{label}`) "
            "RETURN id(n) AS id, "
            "coalesce(n.name, n.entity_name, toString(id(n))) AS name, "
            "coalesce(n.entity_type, n.type, 'unknown') AS entity_type "
            "LIMIT $limit"
        )
        catalog: list[dict[str, Any]] = []
        async with driver.session(database=database, default_access_mode="READ") as session:
            result = await session.run(query, limit=self.candidate_limit)
            async for row in result:
                catalog.append(
                    {
                        "id": str(row["id"]),
                        "name": str(row["name"]),
                        "entity_type": row["entity_type"],
                    }
                )
        return catalog

    async def _embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(self.embedding_model)
        return await asyncio.to_thread(
            self._embedding_model.encode,
            list(texts),
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
