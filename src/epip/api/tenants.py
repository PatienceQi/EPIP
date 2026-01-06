"""FastAPI router exposing tenant administration endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from epip.admin import Tenant, TenantRepository, TenantStatus
from epip.api.dependencies import get_tenant_repository

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


def _build_tenant_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse.model_validate(tenant)


class TenantCreateRequest(BaseModel):
    """Payload accepted when provisioning a new tenant."""

    tenant_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    status: TenantStatus = TenantStatus.ACTIVE
    config: dict[str, Any] = Field(default_factory=dict)


class TenantUpdateRequest(BaseModel):
    """Partial tenant update payload."""

    name: str | None = Field(default=None, min_length=1)
    status: TenantStatus | None = None
    config: dict[str, Any] | None = None


class TenantResponse(BaseModel):
    """Tenant representation returned via the API."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    name: str
    status: TenantStatus
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreateRequest,
    repository: TenantRepository = Depends(get_tenant_repository),
) -> TenantResponse:
    """Create a tenant record."""

    tenant = Tenant(
        tenant_id=payload.tenant_id,
        name=payload.name,
        status=payload.status,
        config=payload.config,
    )
    try:
        created = await repository.create(tenant)
    except ValueError as exc:  # Duplicate tenant
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _build_tenant_response(created)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    repository: TenantRepository = Depends(get_tenant_repository),
) -> TenantResponse:
    """Fetch a tenant by its identifier."""

    tenant = await repository.get(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _build_tenant_response(tenant)


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    payload: TenantUpdateRequest,
    repository: TenantRepository = Depends(get_tenant_repository),
) -> TenantResponse:
    """Update mutable tenant attributes."""

    tenant = await repository.get(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if payload.name is not None:
        tenant.name = payload.name
    if payload.status is not None:
        tenant.status = payload.status
    if payload.config is not None:
        tenant.config = payload.config

    updated = await repository.update(tenant)
    return _build_tenant_response(updated)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_tenant(
    tenant_id: str,
    repository: TenantRepository = Depends(get_tenant_repository),
) -> Response:
    """Remove a tenant."""

    deleted = await repository.delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    repository: TenantRepository = Depends(get_tenant_repository),
) -> list[TenantResponse]:
    """List all tenants currently registered."""

    tenants = await repository.list_all()
    return [_build_tenant_response(tenant) for tenant in tenants]


__all__ = ["router", "TenantCreateRequest", "TenantUpdateRequest", "TenantResponse"]
