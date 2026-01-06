# Story 5.1: 多租户隔离

**Epic**: Epic 5 - 系统管理与部署
**优先级**: P1
**估算**: 中型

---

## 用户故事

**作为** 系统管理员，
**我想要** 支持多租户隔离，
**以便** 不同组织的数据相互独立、安全隔离。

---

## 验收标准

### AC1: 租户上下文管理
- [ ] 实现租户标识（tenant_id）
- [ ] 请求级别租户上下文注入
- [ ] 租户信息存储和验证
- [ ] 支持租户元数据配置

### AC2: 数据隔离
- [ ] KG 数据按租户隔离（Neo4j 标签或分区）
- [ ] 缓存键包含租户前缀
- [ ] 文件存储按租户目录
- [ ] 查询自动添加租户过滤

### AC3: API 租户路由
- [ ] 从请求头提取租户标识
- [ ] 租户中间件验证
- [ ] 租户不存在返回 403
- [ ] 支持租户切换（管理员）

### AC4: 租户管理 API
- [ ] 创建租户 POST /api/tenants
- [ ] 获取租户 GET /api/tenants/{id}
- [ ] 更新租户 PUT /api/tenants/{id}
- [ ] 删除租户 DELETE /api/tenants/{id}

---

## 技术任务

### Task 5.1.1: 租户模型和上下文
```python
# src/epip/admin/tenant.py

from dataclasses import dataclass
from enum import Enum

class TenantStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

@dataclass
class Tenant:
    tenant_id: str
    name: str
    status: TenantStatus
    config: dict
    created_at: datetime
    updated_at: datetime

class TenantContext:
    """线程/协程本地租户上下文"""
    _current: contextvars.ContextVar[Tenant | None]

    @classmethod
    def get_current(cls) -> Tenant | None

    @classmethod
    def set_current(cls, tenant: Tenant) -> None

class TenantRepository:
    """租户持久化"""
    async def create(self, tenant: Tenant) -> Tenant
    async def get(self, tenant_id: str) -> Tenant | None
    async def update(self, tenant: Tenant) -> Tenant
    async def delete(self, tenant_id: str) -> bool
    async def list_all(self) -> list[Tenant]
```

### Task 5.1.2: 租户中间件
```python
# src/epip/api/middleware/tenant.py

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class TenantMiddleware(BaseHTTPMiddleware):
    """从请求中提取并验证租户"""

    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id:
            return JSONResponse(status_code=403, content={"detail": "Tenant required"})
        # 验证租户并设置上下文
        ...
```

---

## 测试用例

### 单元测试
- [ ] 测试 TenantContext 上下文管理
- [ ] 测试 TenantRepository CRUD
- [ ] 测试租户中间件验证

### 集成测试
- [ ] 测试多租户数据隔离
- [ ] 测试 API 租户路由

---

## 依赖关系

- **前置**: Epic 4（核心功能完成）
- **后置**: Story 5.2（RBAC 基于租户）
