"""Role-based access control primitives."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum


class Permission(str, Enum):
    """Supported permissions that can be assigned to roles."""

    KG_READ = "kg:read"
    KG_WRITE = "kg:write"
    QUERY_EXECUTE = "query:execute"
    CACHE_MANAGE = "cache:manage"
    ADMIN_ALL = "*:*"


@dataclass(slots=True)
class Role:
    """Role metadata and the permissions granted by the role."""

    role_id: str
    name: str
    permissions: set[Permission] = field(default_factory=set)
    parent_role: str | None = None


@dataclass(slots=True)
class User:
    """User profile tied to one or more roles."""

    user_id: str
    username: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)
    is_active: bool = True


class RoleRepository:
    """In-memory repository storing predefined and custom roles."""

    def __init__(self, roles: Iterable[Role] | None = None) -> None:
        self._roles: dict[str, Role] = {}
        self._bootstrap_defaults()
        if roles:
            for role in roles:
                self.add_role(role)

    def _bootstrap_defaults(self) -> None:
        viewer = Role(
            role_id="viewer",
            name="Viewer",
            permissions={Permission.KG_READ, Permission.QUERY_EXECUTE},
        )
        editor = Role(
            role_id="editor",
            name="Editor",
            permissions={Permission.KG_WRITE},
            parent_role="viewer",
        )
        admin = Role(
            role_id="admin",
            name="Admin",
            permissions={Permission.CACHE_MANAGE, Permission.ADMIN_ALL},
            parent_role="editor",
        )
        for role in (viewer, editor, admin):
            self._roles.setdefault(role.role_id, role)

    def add_role(self, role: Role) -> Role:
        """Store or update a role definition."""

        self._roles[role.role_id] = role
        return role

    def get_role(self, role_id: str) -> Role | None:
        """Return the role matching the provided identifier."""

        return self._roles.get(role_id)

    def list_roles(self) -> list[Role]:
        """Expose all registered roles."""

        return list(self._roles.values())


class UserRepository:
    """In-memory repository that stores users and their roles."""

    def __init__(self, users: Iterable[User] | None = None) -> None:
        self._users: dict[str, User] = {}
        if users:
            for user in users:
                self.add_user(user)

    def add_user(self, user: User) -> User:
        """Persist a user in the repository."""

        self._users[user.user_id] = user
        return user

    def get_user(self, user_id: str) -> User | None:
        """Return a user if present."""

        return self._users.get(user_id)

    def update_user(self, user: User) -> User:
        """Replace an existing user entry."""

        if user.user_id not in self._users:
            raise KeyError(f"User {user.user_id} does not exist")
        self._users[user.user_id] = user
        return user

    def list_users(self) -> list[User]:
        """Return all stored users."""

        return list(self._users.values())


class RBACService:
    """Service for evaluating permissions and managing user roles."""

    def __init__(self, role_repository: RoleRepository, user_repository: UserRepository) -> None:
        self._roles = role_repository
        self._users = user_repository

    def has_permission(self, user: User, permission: Permission) -> bool:
        """Check whether the user possesses the provided permission."""

        if not user.is_active:
            return False
        permissions = self.get_user_permissions(user)
        return Permission.ADMIN_ALL in permissions or permission in permissions

    def get_user_permissions(self, user: User) -> set[Permission]:
        """Return the flattened permission set for the user."""

        if not user.is_active:
            return set()
        permissions: set[Permission] = set()
        for role_id in user.roles:
            permissions.update(self._collect_role_permissions(role_id, visited=set()))
        return permissions

    def _collect_role_permissions(self, role_id: str, visited: set[str]) -> set[Permission]:
        if role_id in visited:
            return set()
        visited.add(role_id)
        role = self._roles.get_role(role_id)
        if not role:
            return set()
        permissions = set(role.permissions)
        if role.parent_role:
            permissions.update(self._collect_role_permissions(role.parent_role, visited))
        return permissions

    def assign_role(self, user_id: str, role_id: str) -> None:
        """Assign a role to the target user if both exist."""

        user = self._users.get_user(user_id)
        if user is None:
            raise KeyError(f"User {user_id} does not exist")
        if not self._roles.get_role(role_id):
            raise KeyError(f"Role {role_id} does not exist")
        if role_id not in user.roles:
            user.roles.append(role_id)
            self._users.update_user(user)

    def revoke_role(self, user_id: str, role_id: str) -> None:
        """Remove a role assignment from the target user."""

        user = self._users.get_user(user_id)
        if user is None:
            raise KeyError(f"User {user_id} does not exist")
        if role_id in user.roles:
            user.roles.remove(role_id)
            self._users.update_user(user)


__all__ = [
    "Permission",
    "RBACService",
    "Role",
    "RoleRepository",
    "User",
    "UserRepository",
]
