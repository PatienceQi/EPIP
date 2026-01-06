# Story 5.2: RBAC 权限管理

**Epic**: Epic 5 - 系统管理与部署
**优先级**: P1
**估算**: 中型

---

## 用户故事

**作为** 系统管理员，
**我想要** 基于角色的访问控制，
**以便** 精细化管理用户权限。

---

## 验收标准

### AC1: 角色定义
- [ ] 预定义角色：Admin、Editor、Viewer
- [ ] 自定义角色支持
- [ ] 角色继承机制
- [ ] 角色元数据配置

### AC2: 权限定义
- [ ] 资源级权限（KG、Query、Cache）
- [ ] 操作级权限（Create、Read、Update、Delete）
- [ ] 权限组合（如 kg:read, query:execute）
- [ ] 通配符权限（*:*）

### AC3: 用户角色绑定
- [ ] 用户-角色关联
- [ ] 一个用户多角色
- [ ] 租户级角色绑定
- [ ] 角色有效期

### AC4: 权限检查
- [ ] API 端点权限装饰器
- [ ] 运行时权限验证
- [ ] 权限缓存
- [ ] 权限不足返回 403

### AC5: 审计日志
- [ ] 记录敏感操作
- [ ] 包含操作者、时间、资源
- [ ] 支持日志查询
- [ ] 日志保留策略

---

## 技术任务

### Task 5.2.1: 权限模型
```python
# src/epip/admin/rbac.py

from dataclasses import dataclass
from enum import Enum

class Permission(Enum):
    KG_READ = "kg:read"
    KG_WRITE = "kg:write"
    QUERY_EXECUTE = "query:execute"
    CACHE_MANAGE = "cache:manage"
    ADMIN_ALL = "*:*"

@dataclass
class Role:
    role_id: str
    name: str
    permissions: set[Permission]
    parent_role: str | None = None

@dataclass
class User:
    user_id: str
    username: str
    tenant_id: str
    roles: list[str]
    is_active: bool

class RBACService:
    """RBAC 权限服务"""

    def has_permission(self, user: User, permission: Permission) -> bool
    def get_user_permissions(self, user: User) -> set[Permission]
    def assign_role(self, user_id: str, role_id: str) -> None
    def revoke_role(self, user_id: str, role_id: str) -> None
```

### Task 5.2.2: 权限装饰器
```python
# src/epip/api/auth.py

from functools import wraps
from fastapi import Depends, HTTPException

def require_permission(permission: Permission):
    """权限检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = get_current_user()
            if not rbac_service.has_permission(user, permission):
                raise HTTPException(status_code=403, detail="Permission denied")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

---

## 测试用例

### 单元测试
- [ ] 测试 has_permission()
- [ ] 测试角色继承
- [ ] 测试权限装饰器

### 集成测试
- [ ] 测试 API 权限控制
- [ ] 测试审计日志记录

---

## 依赖关系

- **前置**: Story 5.1（多租户）
- **后置**: Story 5.3（监控）
