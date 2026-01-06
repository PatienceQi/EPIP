"""Utilities for converting structured data into LightRAG-friendly documents."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import structlog

logger = structlog.get_logger()


class DocumentConverter:
    """Convert supported file formats into textual documents."""

    def parquet_to_documents(self, path: Path) -> Iterator[str]:
        """Yield one document per row from a parquet file."""
        df = pd.read_parquet(path)
        source = path.stem
        for _, row in df.iterrows():
            yield self._row_to_document(row, source)

    def _row_to_document(self, row: pd.Series, source: str) -> str:
        """Format a dataframe row into a multi-line document string."""
        lines = [f"Source: {source}"]
        for column, value in row.items():
            if pd.notna(value):
                lines.append(f"{column}: {value}")
        return "\n".join(lines)

    def pdf_to_documents(self, path: Path) -> Iterator[str]:
        """Yield documents for each non-empty PDF page."""
        import pypdf

        reader = pypdf.PdfReader(path)
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            cleaned = text.strip()
            if not cleaned:
                logger.debug("Skipping empty PDF page", file=str(path), page=index + 1)
                continue
            header = f"Source: {path.name} (Page {index + 1})"
            yield f"{header}\n\n{cleaned}"
