# EPIP API 参考

本页基于 `src/epip/api/routes.py`、`src/epip/api/tenants.py`、`src/epip/api/visualization.py`、`src/epip/api/monitoring.py` 与 `src/epip/main.py` 总结所有公开端点。示例默认使用 `http://localhost:8000`，请根据部署环境调整。

## 1. 认证与多租户隔离

EPIP 通过 `TenantMiddleware` 要求大部分请求携带租户标识。

| 请求头 | 是否必填 | 说明 | 示例 |
| --- | --- | --- | --- |
| `X-Tenant-ID` | 是（除 `/monitoring/*` 端点外） | 指定当前租户，必须是处于 ACTIVE 状态的租户，否则请求会被拒绝 | `acme-prod` |

- 当缺少请求头或租户被禁用时会返回 `403`，部分基础监控端点在 `public_paths` 中可匿名调用。
- 如需区分不同来源，可结合 `QueryRequest.source` 字段记录 `api`、`ui` 等入口。

## 2. 端点分组总览

| 分组 | 方法 | 路径 | 描述 |
| --- | --- | --- | --- |
| 查询 | GET | `/` | 服务探活欢迎语（需租户头） |
| 查询 | GET | `/api/status` | 返回部署环境与版本号 |
| 查询 | POST | `/api/query` | 执行查询编排管线并返回结果与元数据 |
| 缓存 | GET | `/api/cache/stats` | 查看查询缓存命中情况 |
| 缓存 | POST | `/api/cache/clear` | 按模式清理缓存条目 |
| 租户 | POST | `/api/tenants/` | 创建租户 |
| 租户 | GET | `/api/tenants/{tenant_id}` | 查询单个租户 |
| 租户 | PUT | `/api/tenants/{tenant_id}` | 更新租户信息 |
| 租户 | DELETE | `/api/tenants/{tenant_id}` | 删除租户 |
| 租户 | GET | `/api/tenants/` | 列出租户 |
| 可视化 | GET | `/api/visualization/trace/{trace_id}` | 将推理轨迹转换为前端图数据 |
| 可视化 | GET | `/api/visualization/verification/{answer_id}` | 将验证报告导出为图数据 |
| 可视化 | GET | `/api/visualization/evidence/{node_id}` | 查询节点上下文（事实/证据/冲突） |
| 可视化 | POST | `/api/visualization/export` | 导出图为 JSON/SVG/Markdown |
| 监控 | GET | `/health` | 统一健康检查（含 Neo4j/Redis） |
| 监控 | GET | `/monitoring/metrics` | Prometheus 指标（公开） |
| 监控 | GET | `/monitoring/health/live` | Liveness Probe（公开） |
| 监控 | GET | `/monitoring/health/ready` | Readiness Probe（公开） |

## 3. 标准错误码

| 状态码 | 说明 | 常见触发条件 |
| --- | --- | --- |
| 401 Unauthorized | 未认证或凭据无效 | 未来若接入额外认证层时触发。当前以网关/反向代理为准 |
| 403 Forbidden | 缺失 `X-Tenant-ID`、租户不存在或状态不是 ACTIVE | `TenantMiddleware` 拦截的大多数失败 |
| 404 Not Found | 资源不存在 | 查询不存在的租户、轨迹、验证报告、节点等 |
| 422 Unprocessable Entity | 参数校验失败 | Pydantic 校验（必填字段缺失、格式不符） |
| 500 Internal Server Error | 未捕获的服务端异常 | 下游调用失败、内部逻辑错误 |

## 4. 端点详情与示例

所有 JSON 均使用 UTF-8 编码；除监控类端点外，示例默认添加 `-H 'X-Tenant-ID: acme-prod'`。

### 4.1 查询

#### GET `/`
- **说明**：最简单的可达性测试，返回版本号。
- **请求示例**：

```http
GET / HTTP/1.1
Host: localhost:8000
X-Tenant-ID: acme-prod
```

- **响应示例**：

```json
{
  "message": "EPIP API",
  "version": "1.2.3"
}
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/' \
  -H 'X-Tenant-ID: acme-prod'
```

#### GET `/api/status`
- **说明**：展示部署环境与版本。
- **响应示例**：

```json
{
  "environment": "production",
  "version": "1.2.3"
}
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/api/status' \
  -H 'X-Tenant-ID: acme-prod'
```

#### POST `/api/query`
- **说明**：执行解析→实体链接→规划→查询→计划序列化的轻量编排流程。
- **请求体示例**：

```json
{
  "query": "本季度亚太公共政策重点有哪些?",
  "source": "portal"
}
```

- **响应示例**：

```json
{
  "result": "亚太团队聚焦数据跨境与供应链韧性，详见附录。",
  "metadata": {
    "source": "portal",
    "intent": "policy_brief",
    "complexity": "medium",
    "plan": {
      "steps": [
        {"id": "parse", "description": "解析实体"},
        {"id": "retrieve", "description": "检索图谱"},
        {"id": "aggregate", "description": "融合回答"}
      ]
    }
  }
}
```

- **curl**：

```bash
curl -X POST 'http://localhost:8000/api/query' \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: acme-prod' \
  -d '{
        "query": "本季度亚太公共政策重点有哪些?",
        "source": "portal"
      }'
```

### 4.2 缓存

#### GET `/api/cache/stats`
- **说明**：查看查询缓存命中率与内存占用。
- **响应示例**：

```json
{
  "hits": 128,
  "misses": 32,
  "hit_rate": 0.8,
  "size": 560,
  "memory_usage": 10485760
}
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/api/cache/stats' \
  -H 'X-Tenant-ID: acme-prod'
```

#### POST `/api/cache/clear`
- **说明**：按 glob 模式清空缓存 key。
- **请求体示例**：

```json
{
  "pattern": "session:2024Q1:*"
}
```

- **响应示例**：

```json
{
  "pattern": "session:2024Q1:*",
  "cleared": 42
}
```

- **curl**：

```bash
curl -X POST 'http://localhost:8000/api/cache/clear' \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: acme-prod' \
  -d '{"pattern":"session:2024Q1:*"}'
```

### 4.3 租户

#### POST `/api/tenants/`
- **说明**：创建租户，`tenant_id` 必须唯一。
- **请求体示例**：

```json
{
  "tenant_id": "acme-prod",
  "name": "Acme Production",
  "status": "ACTIVE",
  "config": {
    "neo4j_db": "policy",
    "features": ["kg", "verification"]
  }
}
```

- **响应示例**（201）：

```json
{
  "tenant_id": "acme-prod",
  "name": "Acme Production",
  "status": "ACTIVE",
  "config": {
    "neo4j_db": "policy",
    "features": ["kg", "verification"]
  },
  "created_at": "2024-05-10T03:21:09.000Z",
  "updated_at": "2024-05-10T03:21:09.000Z"
}
```

- **curl**：

```bash
curl -X POST 'http://localhost:8000/api/tenants/' \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: platform-admin' \
  -d @tenant.json
```

#### GET `/api/tenants/{tenant_id}`
- **说明**：查询指定租户。

- **响应示例**：同上。

- **curl**：

```bash
curl -X GET 'http://localhost:8000/api/tenants/acme-prod' \
  -H 'X-Tenant-ID: platform-admin'
```

#### PUT `/api/tenants/{tenant_id}`
- **说明**：支持部分字段更新。
- **请求体示例**：

```json
{
  "name": "Acme Global",
  "status": "ACTIVE",
  "config": {
    "features": ["kg", "viz"],
    "retention_days": 30
  }
}
```

- **响应示例**：返回更新后的完整租户信息。

- **curl**：

```bash
curl -X PUT 'http://localhost:8000/api/tenants/acme-prod' \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: platform-admin' \
  -d @tenant-update.json
```

#### DELETE `/api/tenants/{tenant_id}`
- **说明**：删除租户，成功返回 `204 No Content`。

- **curl**：

```bash
curl -X DELETE 'http://localhost:8000/api/tenants/acme-prod' \
  -H 'X-Tenant-ID: platform-admin'
```

#### GET `/api/tenants/`
- **说明**：列出全部租户。
- **响应示例**：

```json
[
  {
    "tenant_id": "acme-prod",
    "name": "Acme Production",
    "status": "ACTIVE",
    "config": {}
  },
  {
    "tenant_id": "beta-lab",
    "name": "Beta Lab",
    "status": "PAUSED",
    "config": {"feature_flags": ["viz"]}
  }
]
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/api/tenants/' \
  -H 'X-Tenant-ID: platform-admin'
```

### 4.4 可视化

#### GET `/api/visualization/trace/{trace_id}`
- **说明**：将推理轨迹转换为 D3 兼容的节点/连线。
- **响应示例**：

```json
{
  "nodes": [
    {"id": "trace:root", "label": "Query", "type": "query"},
    {"id": "trace:node-1", "label": "Retrieve facts", "type": "action"}
  ],
  "links": [
    {"source": "trace:root", "target": "trace:node-1", "label": "leads_to"}
  ],
  "metadata": {"trace_id": "trace-123"}
}
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/api/visualization/trace/trace-123' \
  -H 'X-Tenant-ID: acme-prod'
```

#### GET `/api/visualization/verification/{answer_id}`
- **说明**：根据验证报告生成图数据。
- **响应示例**：

```json
{
  "nodes": [
    {"id": "answer:42", "label": "Answer 42", "type": "answer", "confidence": 0.92},
    {"id": "fact:policy-1", "label": "跨境数据条例", "type": "fact"}
  ],
  "links": [
    {"source": "answer:42", "target": "fact:policy-1", "label": "supports"}
  ],
  "metadata": {"answer_id": "42"}
}
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/api/visualization/verification/42' \
  -H 'X-Tenant-ID: acme-prod'
```

#### GET `/api/visualization/evidence/{node_id}`
- **说明**：查询节点上下文；支持 `fact:*`、`evidence:*`、`conflict:*` 与 `answer:*`。
- **响应示例**：

```json
{
  "node_id": "evidence:policy-1:1",
  "label": "2024 年 4 月会议纪要",
  "type": "evidence",
  "confidence": 0.87,
  "metadata": {
    "source_id": "memo-202404",
    "source_type": "document"
  }
}
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/api/visualization/evidence/evidence:policy-1:1' \
  -H 'X-Tenant-ID: acme-prod'
```

#### POST `/api/visualization/export`
- **说明**：把图导出为 JSON/SVG/Markdown；默认 JSON。
- **请求体示例**：

```json
{
  "graph": {
    "nodes": [{"id": "node-1", "label": "Fact"}],
    "links": []
  },
  "format": "markdown",
  "metadata": {
    "generated_by": "analyst-01"
  }
}
```

- **响应示例**：

```json
{
  "format": "markdown",
  "content": "# Visualization Export\n\n- Nodes: 1\n- Edges: 0\n- Metadata: \n  - generated_by: analyst-01"
}
```

- **curl**：

```bash
curl -X POST 'http://localhost:8000/api/visualization/export' \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: acme-prod' \
  -d '{
        "graph": {"nodes": [{"id": "node-1", "label": "Fact"}], "links": []},
        "format": "markdown",
        "metadata": {"generated_by": "analyst-01"}
      }'
```

### 4.5 监控

#### GET `/health`
- **说明**：结合 Neo4j 与 Redis 状态输出综合健康。
- **响应示例**：

```json
{
  "status": "healthy",
  "services": {
    "neo4j": "up",
    "redis": "up"
  }
}
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/health'
```

#### GET `/monitoring/metrics`
- **说明**：Prometheus 文本格式，包含内部指标。
- **响应示例（摘录）**：

```text
epip_requests_total{route="/api/query",status="200"} 345
process_resident_memory_bytes 9.8e+07
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/monitoring/metrics'
```

#### GET `/monitoring/health/live`
- **说明**：K8s liveness probe，无外部依赖。
- **响应示例**：`{"status":"ok"}`

- **curl**：

```bash
curl -X GET 'http://localhost:8000/monitoring/health/live'
```

#### GET `/monitoring/health/ready`
- **说明**：检查 Neo4j/Redis 的 `ping()`，失败则 `status` 为 `error`。
- **响应示例**：

```json
{
  "status": "ok",
  "neo4j": "up",
  "redis": "up"
}
```

- **curl**：

```bash
curl -X GET 'http://localhost:8000/monitoring/health/ready'
```

## 5. 补充说明
- Query/租户/可视化端点若返回 `404`，请检查 ID 是否已通过 `/api/query` 或验证流程写入 `VisualizationMemoryStore`。
- 如果需要自动化脚本，可将 `X-Tenant-ID` 抽象成环境变量：`curl ... -H "X-Tenant-ID: ${TENANT_ID}"`。
- 监控端点已在 `public_paths` 白名单中，方便容器编排系统进行健康探测。
