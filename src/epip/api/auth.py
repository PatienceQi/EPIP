"""Authentication dependencies and permission enforcement helpers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from fastapi import HTTPException, Request, status

from epip.admin.rbac import Permission, RBACService, RoleRepository, User, UserRepository

F = TypeVar("F", bound=Callable[..., Any])

_rbac_service: RBACService | None = None


def configure_rbac_service(service: RBACService | None) -> None:
    """Allow tests or the application to override the RBAC service singleton."""

    global _rbac_service
    _rbac_service = service


def get_rbac_service() -> RBACService:
    """Return the global RBAC service instance, creating it if needed."""

    global _rbac_service
    if _rbac_service is None:
        _rbac_service = RBACService(RoleRepository(), UserRepository())
    return _rbac_service


def get_current_user(request: Request) -> User:
    """Fetch the authenticated user stored on the request state."""

    user = getattr(request.state, "user", None)
    if not isinstance(user, User):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


def require_permission(permission: Permission) -> Callable[[F], F]:
    """Decorator that enforces the given permission before executing the function."""

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                user = _resolve_user(args, kwargs)
                service = _resolve_service(args, kwargs)
                _ensure_permission(service, user, permission)
                return await func(*args, **kwargs)

            return cast(F, async_wrapper)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            user = _resolve_user(args, kwargs)
            service = _resolve_service(args, kwargs)
            _ensure_permission(service, user, permission)
            return func(*args, **kwargs)

        return cast(F, sync_wrapper)

    return decorator


def _resolve_user(args: tuple[Any, ...], kwargs: dict[str, Any]) -> User:
    user = _find_instance(User, args, kwargs)
    if user:
        return user
    request = _find_instance(Request, args, kwargs)
    if request:
        return get_current_user(request)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def _resolve_service(args: tuple[Any, ...], kwargs: dict[str, Any]) -> RBACService:
    service = _find_instance(RBACService, args, kwargs)
    return service or get_rbac_service()


def _ensure_permission(service: RBACService, user: User, permission: Permission) -> None:
    if not service.has_permission(user, permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def _find_instance(expected_type: type[Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    for value in kwargs.values():
        if isinstance(value, expected_type):
            return value
    for value in args:
        if isinstance(value, expected_type):
            return value
    return None


__all__ = [
    "configure_rbac_service",
    "get_current_user",
    "get_rbac_service",
    "require_permission",
]
