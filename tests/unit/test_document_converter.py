"""Tests for the DocumentConverter helpers."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd

from epip.core.document_converter import DocumentConverter


def test_parquet_to_documents_generates_documents(tmp_path):
    converter = DocumentConverter()
    df = pd.DataFrame(
        [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
    )
    parquet_path = tmp_path / "sample.parquet"
    df.to_parquet(parquet_path, index=False)

    documents = list(converter.parquet_to_documents(parquet_path))

    assert len(documents) == 2
    assert documents[0].startswith("Source: sample")
    assert "name: Alice" in documents[0]
    assert "age: 25" in documents[1]


def test_row_to_document_skips_missing_values():
    converter = DocumentConverter()
    row = pd.Series({"company": "Acme", "score": pd.NA})

    document = converter._row_to_document(row, "dataset")

    assert "company: Acme" in document
    assert "score" not in document


def test_pdf_to_documents_skips_empty_pages(monkeypatch, tmp_path):
    converter = DocumentConverter()

    class DummyPage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class DummyReader:
        def __init__(self, path):
            assert path  # ensure path is passed through
            self.pages = [
                DummyPage("First page body"),
                DummyPage("   "),
                DummyPage("Second page body"),
            ]

    dummy_module = SimpleNamespace(PdfReader=DummyReader)
    monkeypatch.setitem(sys.modules, "pypdf", dummy_module)

    pdf_path = tmp_path / "notes.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    documents = list(converter.pdf_to_documents(pdf_path))

    assert len(documents) == 2
    assert "Page 1" in documents[0]
    assert "First page body" in documents[0]
    assert "Page 3" not in documents[0]
    assert "Page 3" in documents[1]
    assert "Second page body" in documents[1]
