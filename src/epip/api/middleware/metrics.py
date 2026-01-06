"""FastAPI middleware that records Prometheus metrics for each request."""

from __future__ import annotations

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from epip.monitoring.metrics import MetricsCollector, metrics_collector


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect latency and status metrics automatically for HTTP traffic."""

    def __init__(self, app: ASGIApp, collector: MetricsCollector | None = None) -> None:
        super().__init__(app)
        self._collector = collector or metrics_collector

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        endpoint = request.url.path
        method = request.method
        self._collector.record_request(method, endpoint, response.status_code, duration)
        return response


__all__ = ["MetricsMiddleware"]
