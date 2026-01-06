[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **admin**

# admin - 多租户管理与权限控制

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

提供多租户隔离、基于角色的访问控制（RBAC）、审计日志记录能力。

核心能力：
- 租户生命周期管理（创建、更新、删除、暂停）
- 租户上下文管理（异步本地存储）
- RBAC 权限控制（角色、权限、资源）
- 审计日志记录（操作追踪、合规性）

---

## 入口与启动

### 主要文件

- `tenant.py` - 租户模型与仓储
- `rbac.py` - RBAC 权限控制
- `audit.py` - 审计日志记录

### 初始化示例

```python
from epip.admin.tenant import Tenant, TenantContext, TenantRepository, TenantStatus
from epip.admin.rbac import RBACManager, Role, Permission
from epip.admin.audit import AuditLogger

# 租户管理
repo = TenantRepository()
tenant = Tenant(
    tenant_id="org-001",
    name="示例组织",
    status=TenantStatus.ACTIVE,
    config={"max_users": 100}
)
await repo.create(tenant)

# 设置当前租户上下文
TenantContext.set_current(tenant)

# RBAC 权限检查
rbac = RBACManager()
has_permission = await rbac.check_permission(
    user_id="user-123",
    resource="knowledge_graph",
    action="read"
)

# 审计日志
audit = AuditLogger()
await audit.log(
    tenant_id=tenant.tenant_id,
    user_id="user-123",
    action="query_executed",
    resource="kg_query",
    metadata={"query": "..."}
)
```

---

## 对外接口

### Tenant

```python
@dataclass
class Tenant:
    tenant_id: str                           # 租户 ID
    name: str                                # 租户名称
    status: TenantStatus                     # 状态（active、suspended、deleted）
    config: dict[str, Any]                   # 租户配置
    created_at: datetime                     # 创建时间
    updated_at: datetime                     # 更新时间
```

### TenantContext

**核心方法**：
- `get_current() -> Tenant | None` - 获取当前租户
- `set_current(tenant: Tenant)` - 设置当前租户
- `clear()` - 清除租户上下文

**实现机制**：
- 使用 `contextvars.ContextVar` 实现异步本地存储
- 每个异步任务拥有独立的租户上下文
- 自动传播到子任务

### TenantRepository

**核心方法**：
- `create(tenant: Tenant) -> Tenant` - 创建租户
- `get(tenant_id: str) -> Tenant | None` - 获取租户
- `update(tenant: Tenant) -> Tenant` - 更新租户
- `delete(tenant_id: str) -> bool` - 删除租户
- `list_all() -> list[Tenant]` - 列出所有租户

**存储实现**：
- 当前使用内存字典（`dict[str, Tenant]`）
- 生产环境应替换为持久化存储（PostgreSQL、MongoDB）

### RBACManager

**核心方法**：
- `check_permission(user_id, resource, action) -> bool` - 权限检查
- `assign_role(user_id, role) -> None` - 分配角色
- `revoke_role(user_id, role) -> None` - 撤销角色
- `get_user_roles(user_id) -> list[Role]` - 获取用户角色

### AuditLogger

**核心方法**：
- `log(tenant_id, user_id, action, resource, metadata) -> None` - 记录审计日志
- `query(tenant_id, filters) -> list[AuditEntry]` - 查询审计日志

---

## 关键依赖与配置

### 依赖项

- `contextvars` - 异步本地存储（Python 标准库）
- `datetime` - 时间戳管理

### 配置参数

- 租户配置（`Tenant.config`）：
  - `max_users` - 最大用户数
  - `max_storage_gb` - 最大存储空间
  - `features` - 启用的功能列表
  - `rate_limits` - 速率限制配置

### 中间件集成

参考 `src/epip/api/middleware/tenant.py`：
```python
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    tenant_id = request.headers.get("X-Tenant-ID")
    tenant = await tenant_repo.get(tenant_id)
    if tenant:
        TenantContext.set_current(tenant)
    response = await call_next(request)
    TenantContext.clear()
    return response
```

---

## 数据模型

### 租户生命周期

```
创建（ACTIVE）
    ↓
正常使用
    ↓
暂停（SUSPENDED）- 可恢复
    ↓
删除（DELETED）- 软删除，保留数据
    ↓
物理删除（可选）- 永久删除
```

### RBAC 模型

```
User（用户）
    ↓ 拥有
Role（角色）
    ↓ 包含
Permission（权限）
    ↓ 作用于
Resource（资源）+ Action（操作）
```

示例：
- 用户 `user-123` 拥有角色 `admin`
- 角色 `admin` 包含权限 `knowledge_graph:*`
- 权限允许对资源 `knowledge_graph` 执行所有操作

---

## 测试与质量

### 测试文件

- `tests/unit/test_multi_tenancy.py` - 单元测试（租户管理、RBAC、审计）

### 测试覆盖

- 租户 CRUD 操作
- 租户上下文隔离
- RBAC 权限检查
- 审计日志记录与查询
- 并发场景下的上下文安全性

---

## 常见问题 (FAQ)

**Q: 如何实现租户数据隔离？**
A: 1) 在数据库查询中添加 `tenant_id` 过滤；2) 使用中间件自动注入租户上下文；3) 在 Neo4j 中使用节点标签或属性隔离。

**Q: 租户上下文在异步任务中如何传播？**
A: `contextvars.ContextVar` 会自动传播到 `asyncio.create_task()` 创建的子任务，无需手动传递。

**Q: 如何实现租户级配额限制？**
A: 在 `Tenant.config` 中定义配额，在业务逻辑中检查并拒绝超限请求。

**Q: RBAC 如何扩展？**
A: 1) 定义新的资源类型；2) 添加新的操作类型；3) 创建新的角色与权限映射。

**Q: 审计日志如何持久化？**
A: 当前为内存实现，生产环境应写入时序数据库（InfluxDB、TimescaleDB）或日志系统（Elasticsearch）。

---

## 相关文件清单

```
src/epip/admin/
├── tenant.py              # 租户模型与仓储（98 行）
├── rbac.py                # RBAC 权限控制
├── audit.py               # 审计日志记录
└── __init__.py            # 模块导出
```

---

## 下一步建议

- 实现租户数据库持久化（PostgreSQL）
- 补充 RBAC 细粒度权限（字段级、行级）
- 添加租户配额监控与告警
- 实现审计日志导出（CSV、JSON）
- 集成 SSO 单点登录（SAML、OAuth2）
