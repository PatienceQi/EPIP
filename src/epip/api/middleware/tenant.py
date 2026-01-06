"""Middleware enforcing tenant isolation for every request."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from epip.admin import TenantContext, TenantRepository, TenantStatus


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve the tenant based on the `X-Tenant-ID` header."""

    def __init__(
        self,
        app: ASGIApp,
        repository: TenantRepository | None = None,
        public_paths: Iterable[str] | None = None,
        public_prefixes: Iterable[str] | None = None,
        allow_spa_fallback: bool = False,
    ) -> None:
        super().__init__(app)
        self._repository = repository or TenantRepository()
        self._public_paths = frozenset(public_paths or ())
        self._public_prefixes = tuple(public_prefixes or ())
        self._allow_spa_fallback = allow_spa_fallback

    def _is_public(self, path: str) -> bool:
        """Check if the path is public (no tenant required)."""
        if path in self._public_paths:
            return True
        if any(path.startswith(prefix) for prefix in self._public_prefixes):
            return True
        # SPA fallback: non-API paths without file extensions are likely client routes
        if self._allow_spa_fallback and not path.startswith("/api/") and "." not in path.split("/")[-1]:
            return True
        return False

    async def dispatch(self, request: Request, call_next):
        if self._is_public(request.url.path):
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id:
            return JSONResponse(status_code=403, content={"detail": "Tenant header missing"})

        repository = getattr(request.app.state, "tenant_repository", self._repository)
        tenant = await repository.get(tenant_id)
        if tenant is None or tenant.status is not TenantStatus.ACTIVE:
            return JSONResponse(status_code=403, content={"detail": "Tenant not allowed"})

        TenantContext.set_current(tenant)
        try:
            response = await call_next(request)
        finally:
            TenantContext.clear()
        return response


__all__ = ["TenantMiddleware"]
