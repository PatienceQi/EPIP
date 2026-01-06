"""Unit tests for RBAC services, decorators, and audit logging."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from epip.admin import (
    AuditLogger,
    Permission,
    RBACService,
    RoleRepository,
    User,
    UserRepository,
)
from epip.api.auth import configure_rbac_service, require_permission


@pytest.fixture()
def role_repository() -> RoleRepository:
    return RoleRepository()


@pytest.fixture()
def user_repository() -> UserRepository:
    return UserRepository()


@pytest.fixture()
def rbac_service(role_repository: RoleRepository, user_repository: UserRepository) -> RBACService:
    return RBACService(role_repository, user_repository)


def _make_user(user_repository: UserRepository, user_id: str, roles: list[str]) -> User:
    user = User(
        user_id=user_id,
        username=user_id,
        tenant_id="tenant",
        roles=roles,
    )
    user_repository.add_user(user)
    return user


def _make_request(user: User | None = None) -> Request:
    scope = {"type": "http", "headers": []}
    request = Request(scope)
    if user:
        request.state.user = user
    return request


def test_has_permission_checks_assigned_roles(
    rbac_service: RBACService,
    user_repository: UserRepository,
):
    user = _make_user(user_repository, "alice", ["viewer"])

    assert rbac_service.has_permission(user, Permission.KG_READ) is True
    assert rbac_service.has_permission(user, Permission.KG_WRITE) is False


def test_role_inheritance_expands_permissions(
    rbac_service: RBACService,
    user_repository: UserRepository,
):
    user = _make_user(user_repository, "bob", ["editor"])

    permissions = rbac_service.get_user_permissions(user)
    assert Permission.KG_READ in permissions
    assert Permission.KG_WRITE in permissions
    assert Permission.QUERY_EXECUTE in permissions


@pytest.mark.asyncio()
async def test_require_permission_decorator_enforces_access(
    rbac_service: RBACService,
    user_repository: UserRepository,
):
    user = _make_user(user_repository, "carol", ["viewer"])
    configure_rbac_service(rbac_service)

    @require_permission(Permission.KG_READ)
    async def readable_endpoint(request: Request) -> str:
        return "ok"

    ok_response = await readable_endpoint(_make_request(user))
    assert ok_response == "ok"

    @require_permission(Permission.KG_WRITE)
    async def write_endpoint(request: Request) -> str:
        return "nope"

    with pytest.raises(HTTPException) as exc:
        await write_endpoint(_make_request(user))
    assert exc.value.status_code == 403

    configure_rbac_service(None)


def test_audit_logger_records_and_filters_events():
    logger = AuditLogger()
    event = logger.log("dave", "update", "knowledge_graph", {"field": "value"})

    all_events = logger.query()
    assert len(all_events) == 1
    assert all_events[0] is event

    filtered = logger.query({"user_id": "dave"})
    assert filtered == [event]
    assert logger.query({"action": "delete"}) == []
