"""Tests covering tenant isolation infrastructure."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from epip.admin import Tenant, TenantContext, TenantRepository, TenantStatus
from epip.api.dependencies import get_tenant_repository
from epip.api.middleware.tenant import TenantMiddleware


def _seed(repo: TenantRepository, tenant: Tenant) -> Tenant:
    return asyncio.run(repo.create(tenant))


def _build_test_app(repo: TenantRepository) -> FastAPI:
    app = FastAPI()
    app.state.tenant_repository = repo
    app.add_middleware(TenantMiddleware, repository=repo)

    @app.get("/whoami")
    async def whoami() -> dict[str, str | None]:
        tenant = TenantContext.get_current()
        return {"tenant_id": tenant.tenant_id if tenant else None}

    return app


def test_tenant_context_round_trip():
    TenantContext.clear()
    assert TenantContext.get_current() is None

    tenant = Tenant(tenant_id="ctx", name="Context Tenant")
    TenantContext.set_current(tenant)
    assert TenantContext.get_current() is tenant

    TenantContext.clear()
    assert TenantContext.get_current() is None


@pytest.mark.asyncio()
async def test_tenant_repository_crud_cycle():
    repo = TenantRepository()
    tenant = Tenant(tenant_id="acme", name="Acme Corp")

    created = await repo.create(tenant)
    assert created.created_at == created.updated_at

    fetched = await repo.get("acme")
    assert fetched is tenant

    tenant.name = "Acme Holdings"
    tenant.status = TenantStatus.SUSPENDED
    updated = await repo.update(tenant)
    assert updated.updated_at > created.created_at

    tenants = await repo.list_all()
    assert len(tenants) == 1

    deleted = await repo.delete("acme")
    assert deleted is True
    assert await repo.get("acme") is None


def test_tenant_middleware_enforces_active_status():
    repo = TenantRepository()
    _seed(repo, Tenant(tenant_id="alpha", name="Alpha"))
    _seed(repo, Tenant(tenant_id="beta", name="Beta", status=TenantStatus.SUSPENDED))

    app = _build_test_app(repo)
    client = TestClient(app)

    missing_resp = client.get("/whoami")
    assert missing_resp.status_code == 403

    suspended_resp = client.get("/whoami", headers={"X-Tenant-ID": "beta"})
    assert suspended_resp.status_code == 403

    ok_resp = client.get("/whoami", headers={"X-Tenant-ID": "alpha"})
    assert ok_resp.status_code == 200
    assert ok_resp.json()["tenant_id"] == "alpha"
    assert TenantContext.get_current() is None


@pytest.fixture()
def tenant_api_client(api_client):
    repo = TenantRepository()
    previous_repo = getattr(api_client.app.state, "tenant_repository", None)
    api_client.app.state.tenant_repository = repo
    api_client.app.dependency_overrides[get_tenant_repository] = lambda: repo
    try:
        yield api_client, repo
    finally:
        api_client.app.dependency_overrides.pop(get_tenant_repository, None)
        if previous_repo is not None:
            api_client.app.state.tenant_repository = previous_repo
        elif hasattr(api_client.app.state, "tenant_repository"):
            delattr(api_client.app.state, "tenant_repository")


def test_tenant_api_endpoints_cover_crud(tenant_api_client):
    client, repo = tenant_api_client
    _seed(repo, Tenant(tenant_id="root", name="Root Tenant"))
    headers = {"X-Tenant-ID": "root"}

    create_resp = client.post(
        "/api/tenants",
        json={
            "tenant_id": "tenant-1",
            "name": "Tenant One",
            "config": {"region": "apac"},
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["tenant_id"] == "tenant-1"
    assert created["status"] == "active"

    get_resp = client.get("/api/tenants/tenant-1", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Tenant One"

    update_resp = client.put(
        "/api/tenants/tenant-1",
        json={"name": "Tenant Uno", "status": "suspended"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "suspended"

    list_resp = client.get("/api/tenants", headers=headers)
    assert list_resp.status_code == 200
    tenants = list_resp.json()
    assert any(tenant["tenant_id"] == "tenant-1" for tenant in tenants)

    delete_resp = client.delete("/api/tenants/tenant-1", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = client.get("/api/tenants/tenant-1", headers=headers)
    assert missing_resp.status_code == 404
