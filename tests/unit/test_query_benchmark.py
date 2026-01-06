"""Tests for the QueryBenchmark helper."""

from __future__ import annotations

import asyncio

import pytest

from epip.benchmark import QueryBenchmark
from epip.cache import CacheConfig, QueryCache, QueryFingerprint


class _DummyRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, query: str) -> str:
        await asyncio.sleep(0)
        self.calls.append(query)
        return f"result::{query}"


@pytest.mark.asyncio
async def test_query_benchmark_tracks_cache_hits_and_latency() -> None:
    runner = _DummyRunner()
    cache = QueryCache(CacheConfig(redis_url="redis://localhost:0/0", default_ttl=60, max_size=10))
    benchmark = QueryBenchmark(runner.__call__, cache=cache, fingerprint=QueryFingerprint())

    queries = ["alpha", "alpha", "beta"]
    results = await benchmark.run(queries, concurrency=1)

    assert len(results) == 3
    assert [sample.cached for sample in results] == [False, True, False]
    assert len(runner.calls) == 2

    stats = benchmark.compute_stats(results)
    assert stats.max >= stats.min >= 0

    report = benchmark.report(results)
    assert "# Query Benchmark Report" in report
    assert "Cache Hit Rate" in report
