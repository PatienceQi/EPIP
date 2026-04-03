"""Tests for the asynchronous KnowledgeGraphBuilder component."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from epip.config import LightRAGConfig
from epip.core.kg_builder import InsertResult, KGBuilder, KGStats


@pytest.fixture(autouse=True)
def stub_embedding(monkeypatch):
    monkeypatch.setattr(
        "epip.core.kg_builder.KGBuilder._build_embedding_func",
        lambda self: object(),
    )


@pytest.fixture(autouse=True)
def stub_llm_backend(monkeypatch):
    backend = MagicMock()
    backend.generate = AsyncMock(return_value="llm-response")
    backend.generate_stream = AsyncMock()
    monkeypatch.setattr("epip.core.kg_builder.create_llm_backend", lambda config: backend)
    return backend


@pytest.fixture(autouse=True)
def stub_query_param(monkeypatch):
    class DummyQueryParam:
        def __init__(self, mode: str) -> None:
            self.mode = mode

    monkeypatch.setattr("epip.core.kg_builder.QueryParam", DummyQueryParam)


@pytest.fixture
def mock_light_rag(monkeypatch):
    instance = MagicMock()
    instance.initialize_storages = AsyncMock()
    instance.ainsert = AsyncMock()
    instance.aquery = AsyncMock(return_value="rag-response")
    rag_cls = MagicMock(return_value=instance)
    monkeypatch.setattr("epip.core.kg_builder.LightRAG", rag_cls)
    return rag_cls, instance


def _build_config(tmp_path) -> LightRAGConfig:
    return LightRAGConfig(
        working_dir=str(tmp_path / "lightrag"),
        graph_storage="networkx",
        chunk_size=256,
        chunk_overlap=32,
        max_tokens=2048,
    )


def test_kg_builder_initializes_with_expected_config(tmp_path, mock_light_rag):
    rag_cls, _ = mock_light_rag
    config = _build_config(tmp_path)

    KGBuilder(config=config)

    assert rag_cls.call_count == 1
    call_kwargs = rag_cls.call_args.kwargs
    assert call_kwargs["working_dir"] == config.working_dir
    assert call_kwargs["graph_storage"] == "NetworkXStorage"
    assert call_kwargs["chunk_token_size"] == config.chunk_size
    assert call_kwargs["chunk_overlap_token_size"] == config.chunk_overlap
    assert call_kwargs["max_total_tokens"] == config.max_tokens


@pytest.fixture
def builder_with_rag(tmp_path, mock_light_rag):
    config = _build_config(tmp_path)
    builder = KGBuilder(config=config)
    rag_cls, rag_instance = mock_light_rag
    return builder, rag_cls, rag_instance


@pytest.mark.asyncio
async def test_insert_documents_reports_stats(tmp_path, builder_with_rag):
    builder, _, rag_instance = builder_with_rag
    stats = KGStats(
        total_entities=3, total_relations=1, entity_types={"person": 3}, relation_types={}
    )
    builder.get_statistics = AsyncMock(return_value=stats)

    first = tmp_path / "doc-a.txt"
    second = tmp_path / "doc-b.txt"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")

    result = await builder.insert_documents([first, second])

    assert rag_instance.initialize_storages.await_count == 1
    assert rag_instance.ainsert.await_count == 2
    call_paths = sorted(call.kwargs["file_paths"] for call in rag_instance.ainsert.await_args_list)
    assert call_paths == [str(first), str(second)]
    payloads = sorted(call.args[0] for call in rag_instance.ainsert.await_args_list)
    assert payloads == ["alpha", "beta"]
    assert result.file_count == 2
    assert result.entity_count == stats.total_entities
    assert result.relation_count == stats.total_relations
    assert not result.errors


@pytest.mark.asyncio
async def test_query_collects_streaming_chunks(builder_with_rag):
    builder, _, rag_instance = builder_with_rag

    async def stream():
        for chunk in ("Hello", " ", "World"):
            yield chunk

    rag_instance.aquery = AsyncMock(return_value=stream())

    response = await builder.query("Explain policy", mode="graph")

    assert response == "Hello World"
    assert rag_instance.aquery.await_count == 1
    query_kwargs = rag_instance.aquery.await_args.kwargs
    assert query_kwargs["param"].mode == "graph"


@pytest.mark.asyncio
async def test_insert_texts_batches_and_collects_errors(builder_with_rag):
    builder, _, rag_instance = builder_with_rag
    stats = KGStats(total_entities=10, total_relations=5, entity_types={}, relation_types={})
    builder.get_statistics = AsyncMock(return_value=stats)
    rag_instance.ainsert = AsyncMock(side_effect=[Exception("boom"), None, None])

    result = await builder.insert_texts(["one", "two", "three"], batch_size=2)

    assert rag_instance.ainsert.await_count == 3
    assert result.file_count == 2
    assert len(result.errors) == 1
    assert "boom" in result.errors[0]


@pytest.mark.asyncio
async def test_insert_from_parquet_combines_conversion_errors(
    monkeypatch, tmp_path, builder_with_rag
):
    builder, _, _ = builder_with_rag
    builder.insert_texts = AsyncMock(
        return_value=InsertResult(
            file_count=1,
            entity_count=7,
            relation_count=3,
            errors=["insert-error"],
        )
    )

    files = [tmp_path / "first.parquet", tmp_path / "second.parquet"]
    for idx, file_path in enumerate(files):
        file_path.write_text(f"file-{idx}", encoding="utf-8")

    call_counter = {"count": 0}

    def fake_parquet_to_documents(self, path):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            raise ValueError("bad parquet")
        return iter([f"doc-from-{path.name}"])

    monkeypatch.setattr(
        "epip.core.document_converter.DocumentConverter.parquet_to_documents",
        fake_parquet_to_documents,
    )

    result = await builder.insert_from_parquet(files, batch_size=25)

    assert builder.insert_texts.await_count == 1
    assert result.file_count == 1
    assert result.entity_count == 7
    assert result.relation_count == 3
    assert any("bad parquet" in error for error in result.errors)
    assert "insert-error" in result.errors


@pytest.mark.asyncio
async def test_insert_from_pdf_handles_extraction_errors(monkeypatch, tmp_path, builder_with_rag):
    builder, _, _ = builder_with_rag
    builder.insert_texts = AsyncMock(
        return_value=InsertResult(
            file_count=2,
            entity_count=11,
            relation_count=4,
            errors=[],
        )
    )

    pdf_files = [tmp_path / "alpha.pdf", tmp_path / "beta.pdf"]
    for file_path in pdf_files:
        file_path.write_text("placeholder", encoding="utf-8")

    def fake_pdf_to_documents(self, path):
        if "alpha" in path.name:
            raise RuntimeError("extraction failed")
        return iter(["doc-a", "doc-b"])

    monkeypatch.setattr(
        "epip.core.document_converter.DocumentConverter.pdf_to_documents",
        fake_pdf_to_documents,
    )

    result = await builder.insert_from_pdf(pdf_files)

    assert builder.insert_texts.await_count == 1
    assert result.file_count == 2
    assert result.entity_count == 11
    assert result.relation_count == 4
    assert any("extraction failed" in error for error in result.errors)
