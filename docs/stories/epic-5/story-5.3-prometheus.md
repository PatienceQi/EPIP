# Story 5.3: Prometheus 监控

**Epic**: Epic 5 - 系统管理与部署
**优先级**: P2
**估算**: 小型

---

## 用户故事

**作为** 运维人员，
**我想要** 系统暴露 Prometheus 监控指标，
**以便** 实时监控系统健康状态和性能。

---

## 验收标准

### AC1: 核心指标
- [ ] 请求总数（epip_requests_total）
- [ ] 请求延迟（epip_request_duration_seconds）
- [ ] 错误率（epip_errors_total）
- [ ] 活跃连接数（epip_active_connections）

### AC2: 业务指标
- [ ] 查询次数（epip_queries_total）
- [ ] 缓存命中率（epip_cache_hit_ratio）
- [ ] KG 节点数（epip_kg_nodes_total）
- [ ] 推理步骤数（epip_reasoning_steps）

### AC3: 指标端点
- [ ] GET /metrics 暴露 Prometheus 格式
- [ ] 支持标签过滤（租户、环境）
- [ ] 健康检查 /health/live 和 /health/ready

### AC4: Grafana 仪表盘
- [ ] 提供预配置仪表盘 JSON
- [ ] 包含关键业务指标面板
- [ ] 支持告警规则配置

---

## 技术任务

### Task 5.3.1: 指标收集器
```python
# src/epip/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# 核心指标
REQUEST_COUNT = Counter(
    "epip_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "epip_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"]
)

# 业务指标
QUERY_COUNT = Counter(
    "epip_queries_total",
    "Total queries executed",
    ["tenant_id", "query_type"]
)

CACHE_HIT_RATIO = Gauge(
    "epip_cache_hit_ratio",
    "Cache hit ratio",
    ["tenant_id"]
)

class MetricsCollector:
    """指标收集器"""

    def record_request(self, method: str, endpoint: str, status: int, duration: float)
    def record_query(self, tenant_id: str, query_type: str)
    def update_cache_ratio(self, tenant_id: str, ratio: float)
```

### Task 5.3.2: 指标中间件
```python
# src/epip/api/middleware/metrics.py

import time
from starlette.middleware.base import BaseHTTPMiddleware

class MetricsMiddleware(BaseHTTPMiddleware):
    """自动记录请求指标"""

    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        metrics.record_request(
            request.method,
            request.url.path,
            response.status_code,
            duration
        )
        return response
```

### Task 5.3.3: 指标端点
```python
# src/epip/api/monitoring.py

from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(tags=["monitoring"])

@router.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@router.get("/health/live")
async def liveness():
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness():
    # 检查依赖服务
    return {"status": "ready", "dependencies": {...}}
```

---

## 测试用例

### 单元测试
- [ ] 测试 MetricsCollector 记录
- [ ] 测试指标格式正确

### 集成测试
- [ ] 测试 /metrics 端点
- [ ] 测试 /health/* 端点

---

## 依赖关系

- **前置**: Story 5.2（RBAC）
- **后置**: 无
