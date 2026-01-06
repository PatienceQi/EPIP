[根目录](../../CLAUDE.md) > [src](../) > [epip](../) > **api**

# API 模块

> 最后更新：2026-01-06T19:33:46+0800

---

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

REST API 层，负责路由、中间件、依赖注入、请求/响应模型定义。

核心能力：
- **路由管理**：定义所有 API 端点
- **中间件**：租户隔离、指标收集
- **依赖注入**：提供数据库客户端、服务实例
- **Schema 定义**：请求/响应模型验证

---

## 入口与启动

主要入口点：
- `src/epip/main.py`：FastAPI 应用入口
- `routes.py`：核心路由定义
- `dependencies.py`：依赖注入工厂

启动命令：
```bash
uvicorn epip.main:app --reload  # 开发模式
make run  # 使用 Makefile
```

---

## 对外接口

### 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 聚合健康检查（应用 + Neo4j + Redis） |
| GET | `/api/status` | 返回部署环境与版本 |
| POST | `/api/query` | 执行查询/检索/推理流水线 |
| GET | `/api/cache/stats` | 查询缓存命中情况 |
| POST | `/api/cache/clear` | 按模式清理缓存 |

### 租户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tenants/` | 列出所有租户 |
| POST | `/api/tenants/` | 创建新租户 |
| GET | `/api/tenants/{tenant_id}` | 获取租户详情 |
| PUT | `/api/tenants/{tenant_id}` | 更新租户信息 |
| DELETE | `/api/tenants/{tenant_id}` | 删除租户 |

### 可视化

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/visualization/trace/{trace_id}` | 输出 ReAct 轨迹图数据 |
| GET | `/api/visualization/verification/{answer_id}` | 输出验证图谱 |
| GET | `/api/visualization/evidence/{node_id}` | 查看证据/冲突上下文 |
| POST | `/api/visualization/export` | 导出图为 JSON/SVG/Markdown |

### 监控

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/monitoring/metrics` | Prometheus 指标（公开） |
| GET | `/monitoring/health/live` | Liveness Probe（公开） |
| GET | `/monitoring/health/ready` | Readiness Probe（公开） |

---

## 关键依赖与配置

### 中间件

1. **TenantMiddleware**：租户隔离
   - 从请求头 `X-Tenant-ID` 提取租户 ID
   - 验证租户状态（ACTIVE / SUSPENDED）
   - 公开路径白名单：`/health`, `/docs`, `/monitoring/*`

2. **MetricsMiddleware**：指标收集
   - 记录请求计数、响应时间、错误率
   - 暴露 Prometheus 指标

### 依赖注入

通过 `dependencies.py` 提供：
- `get_neo4j_client()`：Neo4j 客户端
- `get_redis_client()`：Redis 客户端
- `get_query_engine()`：查询引擎
- `get_kg_builder()`：KG 构建器
- `get_query_cache()`：查询缓存

---

## 数据模型

### QueryRequest

```python
class QueryRequest(BaseModel):
    query: str
    source: str = "api"
    mode: QueryMode = QueryMode.HYBRID
```

### QueryResponse

```python
class QueryResponse(BaseModel):
    result: str
    metadata: dict[str, Any]
```

### HealthResponse

```python
class HealthResponse(BaseModel):
    status: str
    services: ServiceStatus

class ServiceStatus(BaseModel):
    neo4j: str
    redis: str
```

---

## 测试与质量

### 集成测试

- `tests/integration/test_api.py`：核心 API 端点测试
- `tests/integration/test_api_full.py`：完整 API 流程测试
- `tests/integration/test_graph_api.py`：图管理 API 测试
- `tests/integration/test_admin_graph_api.py`：管理员图 API 测试

### 测试覆盖

- 健康检查端点
- 查询流水线
- 缓存管理
- 租户 CRUD
- 可视化数据生成

---

## 常见问题 (FAQ)

**Q: 如何添加新端点？**
A: 在 `routes.py` 中定义新路由，添加对应 schema 到 `schemas/`，更新依赖注入。

**Q: 如何自定义中间件？**
A: 在 `middleware/` 目录创建新中间件，在 `main.py` 中注册。

**Q: 如何处理跨域请求？**
A: 添加 `CORSMiddleware`，配置允许的源、方法、头。

**Q: 如何启用 API 认证？**
A: 实现 `auth.py` 中的认证逻辑，添加依赖到需要保护的端点。

---

## 相关文件清单

```
src/epip/api/
├── __init__.py
├── routes.py              # 核心路由
├── dependencies.py        # 依赖注入
├── auth.py                # 认证逻辑
├── monitoring.py          # 监控端点
├── graph.py               # 图管理 API
├── tenants.py             # 租户管理 API
├── visualization.py       # 可视化 API
├── middleware/
│   ├── tenant.py          # 租户中间件
│   └── metrics.py         # 指标中间件
├── schemas/
│   ├── __init__.py
│   └── graph.py           # 图相关 schema
└── admin/
    ├── __init__.py
    └── graph.py           # 管理员图 API
```

---

## 相关文档

- [API 参考](../../../docs/api-reference.md)
- [架构文档](../../../docs/architecture.md)
- [部署指南](../../../docs/deployment-guide.md)
