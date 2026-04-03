"""Aggregation utilities for ReAct multi-step reasoning."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field

import structlog

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class RankedResult:
    """Ranked result produced after aggregating query outcomes."""

    content: str
    confidence: float
    path_length: int
    source_queries: list[str] = field(default_factory=list)


class ResultAggregator:
    """Aggregate, deduplicate, and rank intermediate reasoning results."""

    _STRATEGIES: dict[str, dict[str, float]] = {
        "confidence": {"confidence": 0.8, "path_length": 0.2},
        "balanced": {"confidence": 0.6, "path_length": 0.25, "coverage": 0.15},
        "coverage": {"confidence": 0.5, "path_length": 0.2, "coverage": 0.3},
    }

    def aggregate(
        self,
        results: Iterable[dict],
        strategy: str = "confidence",
    ) -> list[RankedResult]:
        """Aggregate raw dictionaries into ranked result objects."""
        ranked: list[RankedResult] = []
        for entry in results:
            try:
                content = str(entry.get("content", "")).strip()
            except Exception:
                logger.debug("Skipping malformed result entry", entry=str(entry))
                continue
            if not content:
                continue
            confidence = self._coerce_float(entry.get("confidence", 0.0))
            path_length = self._coerce_int(entry.get("path_length", 0))
            sources = entry.get("source_queries") or entry.get("source_query") or []
            if isinstance(sources, str):
                source_queries = [sources]
            else:
                source_queries = [str(source) for source in sources if source]
            ranked.append(
                RankedResult(
                    content=content,
                    confidence=max(0.0, min(1.0, confidence)),
                    path_length=max(0, path_length),
                    source_queries=list(dict.fromkeys(source_queries)),
                )
            )

        deduplicated = self.deduplicate(ranked)
        weights = self._resolve_strategy(strategy)
        return self.rank(deduplicated, weights)

    def deduplicate(self, results: Iterable[RankedResult]) -> list[RankedResult]:
        """Merge semantically identical results by normalizing their content."""
        buckets: dict[str, RankedResult] = {}
        for result in results:
            normalized = self._normalize_content(result.content)
            if normalized not in buckets:
                buckets[normalized] = RankedResult(
                    content=result.content,
                    confidence=result.confidence,
                    path_length=result.path_length,
                    source_queries=list(result.source_queries),
                )
                continue
            existing = buckets[normalized]
            existing.confidence = max(existing.confidence, result.confidence)
            existing.path_length = min(existing.path_length, result.path_length)
            for query in result.source_queries:
                if query not in existing.source_queries:
                    existing.source_queries.append(query)
        return list(buckets.values())

    def rank(
        self,
        results: Iterable[RankedResult],
        weights: dict[str, float] | None = None,
    ) -> list[RankedResult]:
        """Rank results based on configurable weights."""
        weights = weights or self._STRATEGIES["confidence"]
        ranked_list = list(results)
        if not ranked_list:
            return []
        max_sources = max((len(result.source_queries) for result in ranked_list), default=1)
        coverage_weight = weights.get("coverage", 0.0)
        confidence_weight = weights.get("confidence", 1.0)
        path_weight = weights.get("path_length", 0.0)

        def score(result: RankedResult) -> float:
            coverage_score = len(result.source_queries) / max_sources if max_sources else 0.0
            path_score = 1.0 / (1 + max(result.path_length, 0))
            return (
                confidence_weight * result.confidence
                + path_weight * path_score
                + coverage_weight * coverage_score
            )

        scored = [(score(result), idx, result) for idx, result in enumerate(ranked_list)]
        scored.sort(key=lambda entry: (-entry[0], entry[2].path_length, entry[2].content))

        return [entry[2] for entry in scored]

    def _resolve_strategy(self, strategy: str) -> dict[str, float]:
        if strategy not in self._STRATEGIES:
            logger.debug(
                "Unknown aggregation strategy; falling back to confidence",
                strategy=strategy,
            )
            return self._STRATEGIES["confidence"]
        return self._STRATEGIES[strategy]

    @staticmethod
    def _normalize_content(content: str) -> str:
        return re.sub(r"\s+", " ", content.strip().lower())

    @staticmethod
    def _coerce_float(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _coerce_int(value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def materialize(result: RankedResult) -> dict[str, object]:
        """Return a dictionary representation for structured logging."""
        return asdict(result)
