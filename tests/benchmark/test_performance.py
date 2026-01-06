"""Tests for the performance benchmarking script."""

from __future__ import annotations

import asyncio

import pytest

from epip.cache import CacheConfig
from scripts import benchmark_performance as perf


class _StubCache:
    def __init__(self, config: CacheConfig | None = None) -> None:
        self._store: dict[str, dict[str, object]] = {}
        self.config = config

    async def connect(self) -> None:  # pragma: no cover - compatibility shim
        return None

    async def close(self) -> None:
        self._store.clear()

    async def get(self, key: str) -> dict[str, object] | None:
        return self._store.get(key)

    async def set(self, key: str, value: dict[str, object], ttl: int | None = None) -> None:
        self._store[key] = dict(value)


@pytest.fixture(autouse=True)
def stub_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid touching real Redis during tests by patching QueryCache."""

    monkeypatch.setattr(perf, "QueryCache", _StubCache)


@pytest.fixture
def fast_query() -> perf.QueryFn:
    async def _runner(query: str) -> dict[str, str]:
        await asyncio.sleep(0.01)
        return {"query": query}

    return _runner


@pytest.mark.asyncio
async def test_query_latency_under_threshold(fast_query: perf.QueryFn) -> None:
    metrics = await perf.execute_performance_suite(
        total_queries=8,
        concurrency=4,
        query_fn=fast_query,
        cache_config=CacheConfig(redis_url="redis://stub"),
    )
    assert metrics.latency.p95 < 2000


@pytest.mark.asyncio
async def test_concurrent_queries(fast_query: perf.QueryFn) -> None:
    metrics = await perf.execute_performance_suite(
        total_queries=12,
        concurrency=3,
        query_fn=fast_query,
        cache_config=CacheConfig(redis_url="redis://stub"),
    )
    assert metrics.concurrency_level == perf.CONCURRENCY_VALIDATION_USERS
    assert metrics.concurrency_stats.p50 > 0


@pytest.mark.asyncio
async def test_cache_performance_improvement(fast_query: perf.QueryFn) -> None:
    metrics = await perf.execute_performance_suite(
        total_queries=12,
        concurrency=3,
        query_fn=fast_query,
        cache_config=CacheConfig(redis_url="redis://stub"),
    )
    assert metrics.cache.improvement_factor >= 2.0
    assert metrics.cache.hit_rate >= 0.5


@pytest.mark.asyncio
async def test_throughput_baseline(fast_query: perf.QueryFn) -> None:
    metrics = await perf.execute_performance_suite(
        total_queries=6,
        concurrency=2,
        query_fn=fast_query,
        cache_config=CacheConfig(redis_url="redis://stub"),
    )
    assert metrics.throughput.qps > 1.0
