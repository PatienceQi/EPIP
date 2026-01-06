[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **monitoring**

# monitoring - 监控与指标

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

提供基于 Prometheus 的监控指标收集与暴露能力，支持优雅降级到内存实现。

核心能力：
- Prometheus 指标收集（Counter、Gauge、Histogram）
- 健康检查端点
- 可选依赖的优雅降级（无 `prometheus_client` 时使用内存实现）
- 指标注册与管理

---

## 入口与启动

### 主要文件

- `metrics.py` - Prometheus 指标封装

### 初始化示例

```python
from epip.monitoring.metrics import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest
)

# 创建注册表
registry = CollectorRegistry()

# 定义指标
query_counter = Counter(
    name="epip_queries_total",
    documentation="Total number of queries executed",
    labelnames=["tenant_id", "status"],
    registry=registry
)

query_latency = Histogram(
    name="epip_query_latency_seconds",
    documentation="Query execution latency in seconds",
    labelnames=["tenant_id"],
    registry=registry
)

kg_size = Gauge(
    name="epip_kg_nodes_total",
    documentation="Total number of nodes in knowledge graph",
    labelnames=["tenant_id"],
    registry=registry
)

# 记录指标
query_counter.labels(tenant_id="org-001", status="success").inc()
query_latency.labels(tenant_id="org-001").observe(0.123)
kg_size.labels(tenant_id="org-001").set(1500)

# 暴露指标（FastAPI 端点）
from fastapi import Response

@app.get("/metrics")
async def metrics():
    data = generate_latest(registry)
    return Response(content=data, media_type="text/plain")
```

---

## 对外接口

### CollectorRegistry

**核心方法**：
- `register(metric)` - 注册指标
- `collect()` - 收集所有指标

### Counter

**用途**：单调递增计数器（请求数、错误数）

**核心方法**：
- `labels(**kwargs) -> MetricHandle` - 获取标签化指标
- `inc(amount=1.0)` - 增加计数

### Gauge

**用途**：可增可减的数值（当前连接数、队列长度）

**核心方法**：
- `labels(**kwargs) -> MetricHandle` - 获取标签化指标
- `set(value)` - 设置值
- `inc(amount=1.0)` - 增加值

### Histogram

**用途**：分布统计（延迟、大小）

**核心方法**：
- `labels(**kwargs) -> MetricHandle` - 获取标签化指标
- `observe(value)` - 记录观测值

### generate_latest

**用途**：生成 Prometheus 文本格式指标

**返回**：`bytes`（Prometheus 文本格式）

---

## 关键依赖与配置

### 依赖项

- `prometheus_client` - Prometheus Python 客户端（可选）

### 优雅降级实现

当 `prometheus_client` 不可用时，模块提供轻量级内存实现：
- `CollectorRegistry` - 内存注册表
- `Counter` / `Gauge` / `Histogram` - 内存指标（存储在 `dict`）
- `generate_latest` - 返回空字节串

**降级特性**：
- 保持相同的 API 接口
- 不抛出异常
- 适用于本地开发环境

---

## 数据模型

### 指标命名规范

遵循 Prometheus 命名约定：
- 使用下划线分隔（`epip_queries_total`）
- 包含单位后缀（`_seconds`、`_bytes`、`_total`）
- 使用命名空间前缀（`epip_`）

### 标签设计

常用标签：
- `tenant_id` - 租户 ID
- `status` - 状态（success、error、timeout）
- `query_type` - 查询类型（fact、relation、path）
- `cache_hit` - 缓存命中（true、false）

### 指标示例

```prometheus
# HELP epip_queries_total Total number of queries executed
# TYPE epip_queries_total counter
epip_queries_total{tenant_id="org-001",status="success"} 1234
epip_queries_total{tenant_id="org-001",status="error"} 56

# HELP epip_query_latency_seconds Query execution latency in seconds
# TYPE epip_query_latency_seconds histogram
epip_query_latency_seconds_bucket{tenant_id="org-001",le="0.1"} 100
epip_query_latency_seconds_bucket{tenant_id="org-001",le="0.5"} 450
epip_query_latency_seconds_bucket{tenant_id="org-001",le="+Inf"} 500
epip_query_latency_seconds_sum{tenant_id="org-001"} 123.45
epip_query_latency_seconds_count{tenant_id="org-001"} 500

# HELP epip_kg_nodes_total Total number of nodes in knowledge graph
# TYPE epip_kg_nodes_total gauge
epip_kg_nodes_total{tenant_id="org-001"} 1500
```

---

## 测试与质量

### 测试文件

- `tests/unit/test_monitoring.py` - 单元测试（指标收集、降级、序列化）

### 测试覆盖

- 指标注册与收集
- 标签化指标操作
- 内存实现降级
- Prometheus 文本格式生成
- 并发访问安全性

---

## 常见问题 (FAQ)

**Q: 如何在 FastAPI 中集成 Prometheus？**
A: 参考上述示例，创建 `/metrics` 端点并返回 `generate_latest()` 结果。

**Q: 如何监控特定租户的指标？**
A: 使用 `tenant_id` 标签过滤，例如 `epip_queries_total{tenant_id="org-001"}`。

**Q: 内存实现与 Prometheus 客户端有何区别？**
A: 内存实现仅存储最新值，不支持持久化与聚合；Prometheus 客户端支持完整的指标类型与导出。

**Q: 如何添加自定义指标？**
A: 1) 定义指标（Counter/Gauge/Histogram）；2) 注册到 `registry`；3) 在业务逻辑中记录。

**Q: 如何配置 Prometheus 抓取？**
A: 在 `prometheus.yml` 中添加抓取目标：
```yaml
scrape_configs:
  - job_name: 'epip'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

---

## 相关文件清单

```
src/epip/monitoring/
├── metrics.py             # Prometheus 指标封装（100+ 行）
└── __init__.py            # 模块导出
```

---

## 下一步建议

- 补充健康检查端点（`/health`、`/ready`）
- 添加预定义指标集（查询、缓存、KG、推理）
- 集成 Grafana 仪表盘模板
- 实现指标告警规则（Prometheus Alertmanager）
- 添加分布式追踪（OpenTelemetry）
