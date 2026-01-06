"""Light-RAG knowledge graph builder integration."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

from epip.config import LightRAGConfig
from epip.core.chinese_prompts import apply_chinese_prompts, get_chinese_entity_types
from epip.core.document_converter import DocumentConverter
from epip.core.llm_backend import LLMBackend, create_llm_backend

logger = structlog.get_logger()

# 应用中文优化的 prompt
apply_chinese_prompts()

try:  # Optional imports for storage-specific statistics helpers
    from lightrag.kg.neo4j_impl import Neo4JStorage
except Exception:  # pragma: no cover - neo4j is optional during tests
    Neo4JStorage = None  # type: ignore

try:
    from lightrag.kg.networkx_impl import NetworkXStorage
except Exception:  # pragma: no cover - networkx backend might be absent
    NetworkXStorage = None  # type: ignore

GRAPH_STORAGE_MAP = {
    "neo4j": "Neo4JStorage",
    "networkx": "NetworkXStorage",
}


@dataclass(slots=True)
class InsertResult:
    """Result of a batch insert operation."""

    file_count: int
    entity_count: int
    relation_count: int
    errors: list[str]


@dataclass(slots=True)
class KGStats:
    """Basic knowledge-graph statistics."""

    total_entities: int
    total_relations: int
    entity_types: dict[str, int]
    relation_types: dict[str, int]


class KGBuilder:
    """Wrapper around LightRAG for EPIP."""

    def __init__(
        self,
        config: LightRAGConfig | None = None,
        *,
        backend: LLMBackend | None = None,
    ) -> None:
        self.config = config or LightRAGConfig()
        self._custom_backend = backend
        self._rag: LightRAG | None = None
        self._backend: LLMBackend | None = None
        self._storages_ready = False
        self._init_lock: asyncio.Lock | None = None
        self._embedding_model = None
        self._build_light_rag()

    def _build_light_rag(self) -> None:
        """Instantiate LightRAG with the latest configuration."""
        safe_config = self.config.model_dump()
        if safe_config.get("neo4j_password"):
            safe_config["neo4j_password"] = "***"
        if safe_config.get("openai_api_key"):
            safe_config["openai_api_key"] = "***"
        logger.info("Initializing KGBuilder", config=safe_config)
        self._configure_graph_environment()
        llm_backend = self._custom_backend or create_llm_backend(self.config)
        self._backend = llm_backend

        embedding_func = self._build_embedding_func()
        llm_callable = self._build_llm_callable(llm_backend)
        working_dir = Path(self.config.working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)

        graph_impl = GRAPH_STORAGE_MAP[self.config.graph_storage.lower()]

        self._rag = LightRAG(
            working_dir=str(working_dir),
            graph_storage=graph_impl,
            llm_model_name=self._llm_model_name,
            llm_model_func=llm_callable,
            embedding_func=embedding_func,
            chunk_token_size=self.config.chunk_size,
            chunk_overlap_token_size=self.config.chunk_overlap,
            max_total_tokens=self.config.max_tokens,
            max_parallel_insert=self.config.max_concurrent_llm,  # 控制 LLM 并发
            embedding_batch_num=self.config.max_concurrent_embed,  # 控制嵌入批次
        )
        self._storages_ready = False

    def _configure_graph_environment(self) -> None:
        """Populate environment variables expected by LightRAG storages."""
        if self.config.graph_storage.lower() == "neo4j":
            os.environ["NEO4J_URI"] = self.config.neo4j_uri
            os.environ["NEO4J_USERNAME"] = self.config.neo4j_user
            os.environ["NEO4J_PASSWORD"] = self.config.neo4j_password

        # 设置中文实体类型
        chinese_entity_types = get_chinese_entity_types()
        os.environ["ENTITY_TYPES"] = ",".join(chinese_entity_types)

    def _build_embedding_func(self) -> EmbeddingFunc:
        """Create the embedding function wrapper."""
        import numpy as np
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.config.embedding_api_key,
            base_url=self.config.embedding_base_url,
        )

        async def embed(texts: list[str]):
            response = await client.embeddings.create(
                model=self.config.embedding_model,
                input=texts,
            )
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings)

        return EmbeddingFunc(
            embedding_dim=self.config.embedding_dim,
            max_token_size=self.config.max_tokens,
            func=embed,
        )

    @property
    def _llm_model_name(self) -> str:
        if self.config.llm_backend == "openai":
            return self.config.llm_model
        return self.config.ollama_model

    def _build_llm_callable(self, backend: LLMBackend):
        """Convert backend into a LightRAG-compatible callable."""

        async def llm_func(
            prompt: str,
            *,
            system_prompt: str | None = None,
            history_messages: list[dict[str, str]] | None = None,
            stream: bool = False,
            **kwargs: Any,
        ):
            backend_kwargs = {
                key: value
                for key in ("max_tokens", "temperature", "top_p")
                if (value := kwargs.get(key)) is not None
            }
            if stream:
                return backend.generate_stream(
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    **backend_kwargs,
                )
            return await backend.generate(
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                **backend_kwargs,
            )

        return llm_func

    def _require_rag(self) -> LightRAG:
        if not self._rag:
            raise RuntimeError("LightRAG is not initialized.")
        return self._rag

    async def _ensure_initialized(self) -> None:
        if self._storages_ready:
            return
        if self._init_lock is None:
            self._init_lock = asyncio.Lock()
        async with self._init_lock:
            if not self._storages_ready:
                await self._require_rag().initialize_storages()
                self._storages_ready = True

    async def insert_documents(self, files: Sequence[Path]) -> InsertResult:
        """Insert text documents into LightRAG."""
        texts: list[str] = []
        sources: list[str] = []
        errors: list[str] = []
        for file_path in files:
            path = Path(file_path)
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as exc:
                error_msg = f"Failed to read {path}: {exc}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
            texts.append(content)
            sources.append(str(path))

        successes, insert_errors = await self._insert_text_collection(
            texts,
            batch_size=50,
            file_paths=sources,
        )
        stats = await self.get_statistics()
        return InsertResult(
            file_count=successes,
            entity_count=stats.total_entities,
            relation_count=stats.total_relations,
            errors=[*errors, *insert_errors],
        )

    async def insert_texts(self, texts: Sequence[str], batch_size: int = 50) -> InsertResult:
        """Insert a collection of raw texts."""
        successes, errors = await self._insert_text_collection(
            texts,
            batch_size=batch_size,
        )
        stats = await self.get_statistics()
        return InsertResult(
            file_count=successes,
            entity_count=stats.total_entities,
            relation_count=stats.total_relations,
            errors=errors,
        )

    async def _insert_text_collection(
        self,
        texts: Sequence[str],
        *,
        batch_size: int,
        file_paths: Sequence[str] | None = None,
    ) -> tuple[int, list[str]]:
        """Insert a collection of texts with optional source tracking."""
        if batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        if not texts:
            return 0, []
        if file_paths is not None and len(file_paths) != len(texts):
            raise ValueError("file_paths length must match texts length")

        rag = self._require_rag()
        await self._ensure_initialized()

        errors: list[str] = []
        successes = 0
        batch_texts: list[str] = []
        batch_paths: list[str | None] = []

        for idx, text in enumerate(texts):
            batch_texts.append(text)
            source = str(file_paths[idx]) if file_paths is not None else None
            batch_paths.append(source)
            if len(batch_texts) == batch_size:
                successes += await self._insert_batch(rag, batch_texts, batch_paths, errors)
                batch_texts = []
                batch_paths = []

        if batch_texts:
            successes += await self._insert_batch(rag, batch_texts, batch_paths, errors)

        return successes, errors

    async def _insert_batch(
        self,
        rag: LightRAG,
        batch: Sequence[str],
        batch_paths: Sequence[str | None],
        errors: list[str],
    ) -> int:
        """Insert a batch of texts and capture successes."""
        if len(batch_paths) != len(batch):
            raise ValueError("batch_paths length must match batch length")

        tasks = []
        for idx, text in enumerate(batch):
            kwargs: dict[str, Any] = {}
            source = batch_paths[idx]
            if source:
                kwargs["file_paths"] = source
            tasks.append(rag.ainsert(text, **kwargs))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = 0
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                source = batch_paths[idx]
                if source:
                    error_msg = f"Insertion failed for {source}: {result}"
                else:
                    snippet = batch[idx].replace("\n", " ")[:120]
                    error_msg = f"Insertion failed for text '{snippet}': {result}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
            if batch_paths[idx]:
                logger.info("Document inserted", source=batch_paths[idx])
            successes += 1
        return successes

    async def insert_from_parquet(
        self, parquet_files: Sequence[Path], batch_size: int = 50
    ) -> InsertResult:
        """Insert LightRAG documents converted from parquet files."""
        converter = DocumentConverter()
        errors: list[str] = []
        documents: list[str] = []

        for file_path in parquet_files:
            path = Path(file_path)
            try:
                documents.extend(converter.parquet_to_documents(path))
            except Exception as exc:
                error_msg = f"Failed to convert parquet {path}: {exc}"
                logger.error(error_msg)
                errors.append(error_msg)

        if not documents:
            stats = await self.get_statistics()
            return InsertResult(
                file_count=0,
                entity_count=stats.total_entities,
                relation_count=stats.total_relations,
                errors=errors,
            )

        insert_result = await self.insert_texts(documents, batch_size=batch_size)
        return InsertResult(
            file_count=insert_result.file_count,
            entity_count=insert_result.entity_count,
            relation_count=insert_result.relation_count,
            errors=[*errors, *insert_result.errors],
        )

    async def insert_from_pdf(self, pdf_files: Sequence[Path]) -> InsertResult:
        """Insert LightRAG documents extracted from PDF files."""
        converter = DocumentConverter()
        errors: list[str] = []
        documents: list[str] = []

        for file_path in pdf_files:
            path = Path(file_path)
            try:
                documents.extend(converter.pdf_to_documents(path))
            except Exception as exc:
                error_msg = f"Failed to extract PDF {path}: {exc}"
                logger.error(error_msg)
                errors.append(error_msg)

        if not documents:
            stats = await self.get_statistics()
            return InsertResult(
                file_count=0,
                entity_count=stats.total_entities,
                relation_count=stats.total_relations,
                errors=errors,
            )

        insert_result = await self.insert_texts(documents)
        return InsertResult(
            file_count=insert_result.file_count,
            entity_count=insert_result.entity_count,
            relation_count=insert_result.relation_count,
            errors=[*errors, *insert_result.errors],
        )

    async def query(self, question: str, mode: str = "mix") -> str:
        """Execute a LightRAG query."""
        rag = self._require_rag()
        await self._ensure_initialized()
        response = await rag.aquery(question, param=QueryParam(mode=mode))
        if isinstance(response, str):
            return response
        # Streaming responses return async iterators.
        chunks = []
        async for chunk in response:
            chunks.append(chunk)
        return "".join(chunks)

    async def get_statistics(self) -> KGStats:
        """Return aggregate KG statistics."""
        rag = self._require_rag()
        await self._ensure_initialized()
        storage = getattr(rag, "chunk_entity_relation_graph", None)

        if Neo4JStorage and isinstance(storage, Neo4JStorage):
            return await self._collect_neo4j_stats(storage)

        if NetworkXStorage and isinstance(storage, NetworkXStorage):
            return await self._collect_networkx_stats(storage)

        logger.warning("Graph storage stats unavailable; returning defaults.")
        return KGStats(0, 0, {}, {})

    async def _collect_neo4j_stats(self, storage) -> KGStats:
        if getattr(storage, "_driver", None) is None:
            await storage.initialize()
        driver = storage._driver
        if driver is None:
            return KGStats(0, 0, {}, {})
        label = storage._get_workspace_label()
        database = getattr(storage, "_DATABASE", None)

        async with driver.session(database=database, default_access_mode="READ") as session:
            node_result = await session.run(f"MATCH (n:`{label}`) RETURN count(n) AS total")
            node_record = await node_result.single()
            await node_result.consume()
            total_entities = node_record["total"] if node_record else 0

            entity_type_result = await session.run(
                f"""
                MATCH (n:`{label}`)
                WITH coalesce(n.entity_type, 'unknown') AS entity_type, count(*) AS total
                RETURN entity_type, total
                """
            )
            entity_types: dict[str, int] = {}
            async for row in entity_type_result:
                entity_types[row["entity_type"]] = row["total"]
            await entity_type_result.consume()

            relation_result = await session.run(
                f"MATCH (:`{label}`)-[r:DIRECTED]-(:`{label}`) RETURN count(r) AS total"
            )
            relation_record = await relation_result.single()
            await relation_result.consume()
            total_relations = relation_record["total"] if relation_record else 0

            relation_type_result = await session.run(
                f"""
                MATCH (:`{label}`)-[r:DIRECTED]-(:`{label}`)
                WITH coalesce(r.relation_type, 'unknown') AS relation_type, count(*) AS total
                RETURN relation_type, total
                """
            )
            relation_types: dict[str, int] = {}
            async for row in relation_type_result:
                relation_types[row["relation_type"]] = row["total"]
            await relation_type_result.consume()

        return KGStats(
            total_entities=total_entities,
            total_relations=total_relations,
            entity_types=entity_types,
            relation_types=relation_types,
        )

    async def _collect_networkx_stats(self, storage) -> KGStats:
        graph = await storage._get_graph()
        entity_types: dict[str, int] = {}
        for _, data in graph.nodes(data=True):
            entity_type = data.get("entity_type", "unknown")
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

        relation_types: dict[str, int] = {}
        for _, _, data in graph.edges(data=True):
            relation_type = data.get("relation_type", "unknown")
            relation_types[relation_type] = relation_types.get(relation_type, 0) + 1

        return KGStats(
            total_entities=graph.number_of_nodes(),
            total_relations=graph.number_of_edges(),
            entity_types=entity_types,
            relation_types=relation_types,
        )

    def configure(self, **params: Any) -> None:
        """Update configuration and re-create LightRAG."""
        backend_sentinel = object()
        backend_override = params.pop("backend", backend_sentinel)
        if params:
            merged = self.config.model_dump()
            merged.update(params)
            self.config = LightRAGConfig(**merged)

        if backend_override is not backend_sentinel:
            if backend_override is None:
                self._custom_backend = None
            elif not isinstance(backend_override, LLMBackend):
                raise TypeError("backend override must be an LLMBackend instance.")
            else:
                self._custom_backend = backend_override

        self._embedding_model = None
        self._build_light_rag()


# Backwards compatibility with previous placeholder class name.
KnowledgeGraphBuilder = KGBuilder
