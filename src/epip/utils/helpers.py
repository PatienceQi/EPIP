"""Generic helper utilities for EPIP."""

from collections.abc import Iterable, Iterator
from typing import Any


def sanitize_identifier(value: str) -> str:
    """Return a lowercase identifier without whitespace."""
    return "_".join(segment for segment in value.strip().lower().split())


def chunk_items(items: Iterable[Any], size: int) -> Iterator[list[Any]]:
    """Yield lists of items bounded by the requested size."""
    if size <= 0:
        raise ValueError("size must be a positive integer")

    chunk: list[Any] = []
    for item in items:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
