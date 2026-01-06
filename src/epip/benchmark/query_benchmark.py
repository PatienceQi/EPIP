"""Utilities for measuring query latency and cache impact."""

from __future__ import annotations

import asyncio
import math
import statistics
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from epip.cache import QueryCache, QueryFingerprint


@dataclass(slots=True)
class BenchmarkResult:
    """Single query execution sample collected during benchmarking."""

    query: str
    latency_ms: float
    cached: bool
    success: bool


@dataclass(slots=True)
class LatencyStats:
    """Aggregated latency percentiles and descriptive statistics."""

    p50: float
    p95: float
    p99: float
    mean: float
    min: float
    max: float


class QueryBenchmark:
    """Benchmark helper that optionally integrates with the query cache."""

    def __init__(
        self,
        query_fn: Callable[[str], Awaitable[object]],
        *,
        cache: QueryCache | None = None,
        fingerprint: QueryFingerprint | None = None,
    ) -> None:
        self._query_fn = query_fn
        self._cache = cache
        self._fingerprint: QueryFingerprint | None = None
        if cache is not None:
            self._fingerprint = fingerprint or QueryFingerprint()

    async def run(self, queries: list[str], concurrency: int = 1) -> list[BenchmarkResult]:
        """Execute the provided queries and record timing information."""
        if not queries:
            return []
        limiter = asyncio.Semaphore(max(1, concurrency))

        async def _bound(query: str) -> BenchmarkResult:
            async with limiter:
                return await self._execute_query(query)

        tasks = [asyncio.create_task(_bound(query)) for query in queries]
        return await asyncio.gather(*tasks)

    def compute_stats(self, results: list[BenchmarkResult]) -> LatencyStats:
        """Compute percentile and descriptive statistics from benchmark samples."""
        latencies = [sample.latency_ms for sample in results]
        if not latencies:
            return LatencyStats(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        latencies.sort()
        return LatencyStats(
            p50=_percentile(latencies, 0.50),
            p95=_percentile(latencies, 0.95),
            p99=_percentile(latencies, 0.99),
            mean=statistics.fmean(latencies),
            min=min(latencies),
            max=max(latencies),
        )

    def report(self, results: list[BenchmarkResult]) -> str:
        """Create a Markdown report for human-friendly inspection."""
        if not results:
            return "# Query Benchmark Report\n\n_No queries executed._"

        stats = self.compute_stats(results)
        total = len(results)
        success_count = sum(1 for sample in results if sample.success)
        cache_hits = sum(1 for sample in results if sample.cached)
        cache_hit_rate = cache_hits / total if total else 0.0
        lines = ["# Query Benchmark Report", ""]
        lines.extend(
            [
                "| Metric | Value |",
                "| --- | --- |",
                f"| Total Queries | {total} |",
                f"| Success Rate | {success_count / total:.2%} |",
                f"| Cache Hit Rate | {cache_hit_rate:.2%} |",
                f"| p50 Latency (ms) | {stats.p50:.2f} |",
                f"| p95 Latency (ms) | {stats.p95:.2f} |",
                f"| p99 Latency (ms) | {stats.p99:.2f} |",
                f"| Mean Latency (ms) | {stats.mean:.2f} |",
                f"| Min Latency (ms) | {stats.min:.2f} |",
                f"| Max Latency (ms) | {stats.max:.2f} |",
            ]
        )

        slowest = sorted(results, key=lambda sample: sample.latency_ms, reverse=True)[:5]
        lines.extend(
            [
                "",
                "## Slowest Queries",
                "",
                "| Query | Latency (ms) | Cached | Success |",
                "| --- | --- | --- | --- |",
            ]
        )
        for sample in slowest:
            lines.append(
                f"| {sample.query} | {sample.latency_ms:.2f} | {sample.cached} | {sample.success} |"
            )
        return "\n".join(lines)

    async def _execute_query(self, query: str) -> BenchmarkResult:
        start = time.perf_counter()
        cached = False
        success = False
        try:
            cached = await self._maybe_serve_from_cache(query)
            success = True
        except Exception:  # pragma: no cover - network/runtime errors are handled above
            success = False
        latency_ms = (time.perf_counter() - start) * 1000
        return BenchmarkResult(query=query, latency_ms=latency_ms, cached=cached, success=success)

    async def _maybe_serve_from_cache(self, query: str) -> bool:
        cache = self._cache
        if cache is None or self._fingerprint is None:
            await self._query_fn(query)
            return False

        key = self._fingerprint.compute(query)
        cached = await cache.get(key)
        if cached is not None:
            return True

        result = await self._query_fn(query)
        await cache.set(key, {"result": str(result), "query": query})
        return False


def _percentile(values: Iterable[float], percentile: float) -> float:
    seq = list(values)
    if not seq:
        return 0.0
    if len(seq) == 1:
        return seq[0]
    rank = (len(seq) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return seq[int(rank)]
    lower_value = seq[lower]
    upper_value = seq[upper]
    return lower_value + (upper_value - lower_value) * (rank - lower)


__all__ = ["BenchmarkResult", "LatencyStats", "QueryBenchmark"]
