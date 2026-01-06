"""Redis-backed cache utilities used by EPIP."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any

try:  # pragma: no cover - optional dependency
    import redis.asyncio as redis_async
except ImportError:  # pragma: no cover - handled via graceful degradation
    redis_async = None

CacheValue = dict[str, Any]


@dataclass(slots=True)
class CacheConfig:
    """Configuration for the query cache backend."""

    redis_url: str = "redis://localhost:6379/0"
    default_ttl: int = 3600
    max_size: int = 10_000
    key_prefix: str = "epip:query:"


@dataclass(slots=True)
class CacheStats:
    """Runtime statistics for the cache layer."""

    hits: int
    misses: int
    hit_rate: float
    size: int
    memory_usage: int


class QueryCache:
    """High-level query cache that gracefully degrades to an in-memory store."""

    def __init__(self, config: CacheConfig | None = None) -> None:
        self._config = config or CacheConfig()
        self._client: Any | None = None
        self._hits = 0
        self._misses = 0
        self._local_cache: OrderedDict[str, tuple[float | None, CacheValue]] = OrderedDict()

    async def connect(self) -> None:
        """Connect to Redis if the client is available."""
        if self._client is not None or redis_async is None:
            return
        try:
            client = redis_async.from_url(self._config.redis_url)
            await client.ping()
        except Exception:  # pragma: no cover - depends on runtime Redis availability
            self._client = None
            return
        self._client = client

    async def close(self) -> None:
        """Dispose of the Redis client if it exists."""
        client = self._client
        if client is None:
            return
        try:  # pragma: no cover - close path varies by redis-py version
            await client.close()
        except Exception:
            pass
        try:  # pragma: no cover - optional clean up
            client.connection_pool.disconnect()
        except Exception:
            pass
        self._client = None

    async def get(self, key: str) -> CacheValue | None:
        """Retrieve a cached payload if present."""
        namespaced = self._with_prefix(key)
        await self.connect()
        value = await self._get_from_redis(namespaced)
        if value is None:
            value = self._get_from_memory(namespaced)
        if value is None:
            self._misses += 1
        else:
            self._hits += 1
            value = dict(value)
        return value

    async def set(self, key: str, value: CacheValue, ttl: int | None = None) -> None:
        """Persist a payload in the cache backend."""
        namespaced = self._with_prefix(key)
        await self.connect()
        ttl_seconds = self._determine_ttl(ttl)
        payload = self._serialize(value)
        if await self._set_in_redis(namespaced, payload, ttl_seconds):
            return
        self._set_in_memory(namespaced, value, ttl_seconds)

    async def delete(self, key: str) -> None:
        """Remove a specific cache key."""
        namespaced = self._with_prefix(key)
        await self.connect()
        if await self._delete_from_redis(namespaced):
            return
        self._local_cache.pop(namespaced, None)

    async def clear(self, pattern: str = "*") -> int:
        """Clear keys matching the provided glob-style pattern."""
        namespaced_pattern = f"{self._config.key_prefix}{pattern}"
        await self.connect()
        removed = await self._clear_from_redis(namespaced_pattern)
        removed += self._clear_from_memory(namespaced_pattern)
        return removed

    async def stats(self) -> CacheStats:
        """Return aggregated statistics for the cache backend."""
        await self.connect()
        size, memory_usage = await self._collect_backend_stats()
        denominator = self._hits + self._misses
        hit_rate = (self._hits / denominator) if denominator > 0 else 0.0
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            hit_rate=hit_rate,
            size=size,
            memory_usage=memory_usage,
        )

    def _with_prefix(self, key: str) -> str:
        if key.startswith(self._config.key_prefix):
            return key
        return f"{self._config.key_prefix}{key}"

    def _now(self) -> float:
        return time.monotonic()

    def _determine_ttl(self, ttl: int | None) -> int:
        value = self._config.default_ttl if ttl is None else ttl
        return value if value > 0 else self._config.default_ttl

    def _serialize(self, value: CacheValue) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _deserialize(self, payload: bytes | str | None) -> CacheValue | None:
        if payload is None:
            return None
        if isinstance(payload, bytes):
            data = payload.decode("utf-8")
        else:
            data = payload
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _purge_expired(self) -> None:
        """Remove expired entries from the in-memory cache."""
        now = self._now()
        expired_keys = [
            key
            for key, (expires_at, _) in self._local_cache.items()
            if expires_at is not None and expires_at <= now
        ]
        for key in expired_keys:
            self._local_cache.pop(key, None)

    async def _get_from_redis(self, key: str) -> CacheValue | None:
        client = self._client
        if client is None:
            return None
        try:
            payload = await client.get(key)
        except Exception:  # pragma: no cover - network failures are environment-specific
            await self.close()
            return None
        return self._deserialize(payload)

    def _get_from_memory(self, key: str) -> CacheValue | None:
        self._purge_expired()
        entry = self._local_cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at is not None and expires_at <= self._now():
            self._local_cache.pop(key, None)
            return None
        # Move to the end to mimic LRU semantics.
        self._local_cache.move_to_end(key)
        return dict(value)

    async def _set_in_redis(self, key: str, payload: bytes, ttl: int) -> bool:
        client = self._client
        if client is None:
            return False
        try:
            await client.set(key, payload, ex=ttl)
            return True
        except Exception:  # pragma: no cover - network failures are environment-specific
            await self.close()
            return False

    def _set_in_memory(self, key: str, value: CacheValue, ttl: int) -> None:
        expires_at: float | None = None
        if ttl > 0:
            expires_at = self._now() + ttl
        self._local_cache[key] = (expires_at, dict(value))
        self._local_cache.move_to_end(key)
        while len(self._local_cache) > self._config.max_size:
            self._local_cache.popitem(last=False)

    async def _delete_from_redis(self, key: str) -> bool:
        client = self._client
        if client is None:
            return False
        try:
            await client.delete(key)
            return True
        except Exception:  # pragma: no cover
            await self.close()
            return False

    async def _clear_from_redis(self, pattern: str) -> int:
        client = self._client
        if client is None:
            return 0
        removed = 0
        try:
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)
                removed += 1
        except Exception:  # pragma: no cover
            await self.close()
            return 0
        return removed

    def _clear_from_memory(self, pattern: str) -> int:
        self._purge_expired()
        keys = [key for key in self._local_cache if fnmatch(key, pattern)]
        for key in keys:
            self._local_cache.pop(key, None)
        return len(keys)

    async def _collect_backend_stats(self) -> tuple[int, int]:
        client = self._client
        if client is not None:
            try:
                size = 0
                async for _ in client.scan_iter(match=f"{self._config.key_prefix}*"):
                    size += 1
                info = await client.info(section="memory")
                memory_usage = int(info.get("used_memory", 0))
                return size, memory_usage
            except Exception:  # pragma: no cover
                await self.close()
        self._purge_expired()
        memory_usage = 0
        for _, value in self._local_cache.values():
            memory_usage += len(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return len(self._local_cache), memory_usage


__all__ = ["CacheConfig", "CacheStats", "QueryCache"]
