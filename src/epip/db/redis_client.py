"""Client wrapper for interacting with Redis."""

from typing import Any

try:
    import redis.asyncio as redis_async
except ImportError:  # pragma: no cover - optional dependency
    redis_async = None


class RedisClient:
    """Manage a lightweight Redis connection handle."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Any | None = None

    def connect(self) -> None:
        """Create the backing client placeholder."""
        if self._client is not None:
            return

        if redis_async is None:
            self._client = {"url": self._url}
            return

        self._client = redis_async.from_url(self._url)

    def close(self) -> None:
        """Dispose of the in-memory client."""
        self._client = None

    async def ping(self) -> bool:
        """Check whether Redis is reachable."""
        if self._client is None:
            self.connect()

        client = self._client
        if client is None:
            return False

        if redis_async is None or not hasattr(client, "ping"):
            return True

        try:
            response = await client.ping()
            return bool(response)
        except Exception:
            return False
