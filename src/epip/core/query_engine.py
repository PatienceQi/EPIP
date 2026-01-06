"""Coordinating orchestrator for EPIP query execution."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from epip.core.data_processor import DataProcessor
from epip.core.hallucination import HallucinationGuard
from epip.core.kg_builder import InsertResult, KGStats, KnowledgeGraphBuilder


class QueryEngine:
    """Coordinate the Light-RAG inspired pipeline."""

    def __init__(
        self,
        *,
        data_processor: DataProcessor,
        kg_builder: KnowledgeGraphBuilder,
        hallucination_guard: HallucinationGuard,
    ) -> None:
        self._data_processor = data_processor
        self._kg_builder = kg_builder
        self._hallucination_guard = hallucination_guard

    def _normalize_question(self, query: str) -> str:
        documents = self._data_processor.prepare_documents([query])
        if not documents:
            raise ValueError("Query cannot be empty.")
        return documents[0]

    async def query(self, question: str, *, mode: str = "mix") -> str:
        """Execute the orchestration pipeline for a single query."""
        normalized_question = self._normalize_question(question)
        response = await self._kg_builder.query(normalized_question, mode=mode)
        return self._hallucination_guard.review_response(response)

    async def insert_documents(self, files: Sequence[Path]) -> InsertResult:
        """Delegate document ingestion to the KG builder."""
        return await self._kg_builder.insert_documents(files)

    async def statistics(self) -> KGStats:
        """Expose aggregated KG statistics."""
        return await self._kg_builder.get_statistics()
