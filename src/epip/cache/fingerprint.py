"""Query fingerprint utilities used by the caching layer."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

_NORMALIZE_PATTERN = re.compile(r"\s+")


def _normalize_params(params: dict[str, Any] | None) -> str:
    if not params:
        return ""
    # Use a deterministic JSON representation to ensure stable hashing.
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


@dataclass(slots=True)
class QueryFingerprint:
    """Generate stable fingerprints for queries and parameter sets."""

    hash_name: str = "sha256"

    def normalize(self, query: str) -> str:
        """Normalize whitespace and casing to improve cache hit rates."""
        collapsed = _NORMALIZE_PATTERN.sub(" ", query).strip()
        return collapsed.casefold()

    def compute(self, query: str, params: dict[str, Any] | None = None) -> str:
        """Return a SHA-based fingerprint for the provided query payload."""
        normalized_query = self.normalize(query)
        serialized_params = _normalize_params(params)
        payload = f"{normalized_query}|{serialized_params}".encode()
        digest = hashlib.new(self.hash_name)
        digest.update(payload)
        return digest.hexdigest()

    def are_equivalent(self, q1: str, q2: str) -> bool:
        """Best-effort semantic equivalence check using normalization."""
        return self.normalize(q1) == self.normalize(q2)


__all__ = ["QueryFingerprint"]
