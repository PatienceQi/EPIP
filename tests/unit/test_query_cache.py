"""Unit tests for the query cache implementation."""

from __future__ import annotations

import asyncio

import pytest

from epip.cache import CacheConfig, QueryCache


@pytest.mark.asyncio
async def test_query_cache_set_get_and_stats() -> None:
    cache = QueryCache(CacheConfig(redis_url="redis://localhost:0/0", max_size=8, default_ttl=60))

    miss = await cache.get("missing")
    assert miss is None

    await cache.set("answer", {"value": 42})
    cached = await cache.get("answer")
    assert cached == {"value": 42}

    stats = await cache.stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.size >= 1


@pytest.mark.asyncio
async def test_query_cache_respects_ttl_and_lru() -> None:
    cache = QueryCache(CacheConfig(redis_url="redis://localhost:0/0", max_size=2, default_ttl=1))
    await cache.set("alpha", {"value": 1}, ttl=1)
    await cache.set("beta", {"value": 2}, ttl=5)

    await asyncio.sleep(1.1)
    assert await cache.get("alpha") is None
    await cache.set("gamma", {"value": 3})

    assert await cache.get("beta") is not None
    assert await cache.get("alpha") is None
    assert await cache.get("gamma") is not None


@pytest.mark.asyncio
async def test_query_cache_clear_supports_patterns() -> None:
    cache = QueryCache(CacheConfig(redis_url="redis://localhost:0/0", max_size=4, default_ttl=60))

    await cache.set("hot:alpha", {"value": 1})
    await cache.set("hot:beta", {"value": 2})
    await cache.set("cold:gamma", {"value": 3})

    removed = await cache.clear("hot*")
    assert removed == 2
    assert await cache.get("hot:alpha") is None
    assert await cache.get("cold:gamma") == {"value": 3}
