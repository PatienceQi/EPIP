"""Tenant domain models, context helpers, and repository implementation."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class TenantStatus(str, Enum):
    """Lifecycle indicator for tenant accounts."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass(slots=True)
class Tenant:
    """Tenant record stored in the repository."""

    tenant_id: str
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


class TenantContext:
    """Provide async-local storage for the active tenant."""

    _current: ContextVar[Tenant | None] = ContextVar("tenant_context", default=None)

    @classmethod
    def get_current(cls) -> Tenant | None:
        """Return the current tenant bound to the execution context."""

        return cls._current.get()

    @classmethod
    def set_current(cls, tenant: Tenant) -> None:
        """Bind the provided tenant to the execution context."""

        cls._current.set(tenant)

    @classmethod
    def clear(cls) -> None:
        """Clear the stored tenant context."""

        cls._current.set(None)


class TenantRepository:
    """In-memory repository backing tenant CRUD operations."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}

    async def create(self, tenant: Tenant) -> Tenant:
        if tenant.tenant_id in self._tenants:
            raise ValueError(f"Tenant {tenant.tenant_id} already exists")
        now = _utcnow()
        tenant.created_at = now
        tenant.updated_at = now
        self._tenants[tenant.tenant_id] = tenant
        return tenant

    async def get(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)

    async def update(self, tenant: Tenant) -> Tenant:
        if tenant.tenant_id not in self._tenants:
            raise KeyError(f"Tenant {tenant.tenant_id} does not exist")
        tenant.updated_at = _utcnow()
        self._tenants[tenant.tenant_id] = tenant
        return tenant

    async def delete(self, tenant_id: str) -> bool:
        return self._tenants.pop(tenant_id, None) is not None

    async def list_all(self) -> list[Tenant]:
        return list(self._tenants.values())


__all__ = [
    "Tenant",
    "TenantContext",
    "TenantRepository",
    "TenantStatus",
]
