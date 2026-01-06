"""Tests for the QueryEngine orchestration logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from epip.core.data_processor import DataProcessor
from epip.core.hallucination import HallucinationGuard
from epip.core.kg_builder import KnowledgeGraphBuilder
from epip.core.query_engine import QueryEngine


@pytest.mark.asyncio
async def test_query_engine_runs_pipeline() -> None:
    data_processor = MagicMock(spec=DataProcessor)
    data_processor.prepare_documents.return_value = ["normalized question"]

    kg_builder = MagicMock(spec=KnowledgeGraphBuilder)
    kg_builder.query = AsyncMock(return_value="light-rag answer")

    hallucination_guard = MagicMock(spec=HallucinationGuard)
    hallucination_guard.review_response.return_value = "reviewed response"

    engine = QueryEngine(
        data_processor=data_processor,
        kg_builder=kg_builder,
        hallucination_guard=hallucination_guard,
    )

    result = await engine.query("  What is the policy update?  ", mode="local")

    data_processor.prepare_documents.assert_called_once_with(["  What is the policy update?  "])
    kg_builder.query.assert_awaited_once_with("normalized question", mode="local")
    hallucination_guard.review_response.assert_called_once_with("light-rag answer")
    assert result == "reviewed response"


@pytest.mark.asyncio
async def test_query_engine_rejects_empty_query() -> None:
    data_processor = MagicMock(spec=DataProcessor)
    data_processor.prepare_documents.return_value = []
    kg_builder = MagicMock(spec=KnowledgeGraphBuilder)
    kg_builder.query = AsyncMock()
    hallucination_guard = MagicMock(spec=HallucinationGuard)

    engine = QueryEngine(
        data_processor=data_processor,
        kg_builder=kg_builder,
        hallucination_guard=hallucination_guard,
    )

    with pytest.raises(ValueError):
        await engine.query("   ")
