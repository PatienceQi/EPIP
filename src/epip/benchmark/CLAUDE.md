[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **benchmark**

# benchmark - 性能基准测试

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

提供查询性能基准测试工具，支持延迟统计、缓存影响分析、并发测试与报告生成。

核心能力：
- 查询延迟测量（p50、p95、p99）
- 缓存命中率统计
- 并发负载测试
- Markdown 报告生成
- 描述性统计（均值、最小值、最大值）

---

## 入口与启动

### 主要文件

- `query_benchmark.py` - 查询基准测试工具

### 初始化示例

```python
from epip.benchmark.query_benchmark import QueryBenchmark, BenchmarkResult, LatencyStats
from epip.cache import QueryCache, QueryFingerprint

# 定义查询函数
async def query_fn(query: str) -> dict:
    # 执行查询逻辑
    return {"result": "..."}

# 初始化基准测试
cache = QueryCache()
fingerprint = QueryFingerprint()
benchmark = QueryBenchmark(
    query_fn=query_fn,
    cache=cache,
    fingerprint=fingerprint
)

# 准备测试查询
queries = [
    "2023年女性创业政策",
    "北京市科技企业补贴",
    "人工智能产业政策"
] * 10  # 重复以测试缓存

# 运行基准测试
results = await benchmark.run(queries, concurrency=5)

# 计算统计
stats = benchmark.compute_stats(results)
print(f"p50: {stats.p50:.2f}ms")
print(f"p95: {stats.p95:.2f}ms")
print(f"p99: {stats.p99:.2f}ms")

# 生成报告
report = benchmark.report(results)
print(report)
```

---

## 对外接口

### QueryBenchmark

**核心方法**：
- `run(queries: list[str], concurrency: int) -> list[BenchmarkResult]` - 执行基准测试
- `compute_stats(results: list[BenchmarkResult]) -> LatencyStats` - 计算统计
- `report(results: list[BenchmarkResult]) -> str` - 生成 Markdown 报告

### BenchmarkResult

```python
@dataclass
class BenchmarkResult:
    query: str                               # 查询文本
    latency_ms: float                        # 延迟（毫秒）
    cached: bool                             # 是否命中缓存
    success: bool                            # 是否成功
```

### LatencyStats

```python
@dataclass
class LatencyStats:
    p50: float                               # 50 百分位延迟（毫秒）
    p95: float                               # 95 百分位延迟（毫秒）
    p99: float                               # 99 百分位延迟（毫秒）
    mean: float                              # 平均延迟（毫秒）
    min: float                               # 最小延迟（毫秒）
    max: float                               # 最大延迟（毫秒）
```

---

## 关键依赖与配置

### 依赖项

- `asyncio` - 异步并发控制
- `statistics` - 统计计算（Python 标准库）
- `epip.cache` - 缓存集成（可选）

### 配置参数

- `concurrency` - 并发查询数（默认 1）
- `cache` - 缓存实例（可选，用于测试缓存影响）
- `fingerprint` - 指纹计算器（可选，与缓存配合使用）

### 并发控制

使用 `asyncio.Semaphore` 限制并发数：
```python
limiter = asyncio.Semaphore(concurrency)
async with limiter:
    result = await execute_query(query)
```

---

## 数据模型

### 基准测试流程

```
准备查询列表
    ↓
创建并发任务（Semaphore 限流）
    ↓
执行查询（记录开始时间）
    ↓
检查缓存命中
    ↓
记录结束时间
    ↓
收集 BenchmarkResult
    ↓
计算统计（LatencyStats）
    ↓
生成报告（Markdown）
```

### 报告格式

```markdown
# Query Benchmark Report

| Metric | Value |
| --- | --- |
| Total Queries | 30 |
| Success Rate | 100.00% |
| Cache Hit Rate | 66.67% |
| p50 Latency (ms) | 45.23 |
| p95 Latency (ms) | 123.45 |
| p99 Latency (ms) | 234.56 |
| Mean Latency (ms) | 67.89 |
| Min Latency (ms) | 12.34 |
| Max Latency (ms) | 345.67 |
```

---

## 测试与质量

### 测试文件

- `tests/benchmark/test_performance.py` - 性能测试（基准测试、回归测试）

### 测试覆盖

- 单查询延迟测量
- 并发查询执行
- 缓存命中率统计
- 统计计算准确性
- 报告生成格式
- 异常处理

---

## 常见问题 (FAQ)

**Q: 如何选择合适的并发数？**
A: 建议从 1 开始，逐步增加到 5、10、20，观察延迟与成功率变化。

**Q: 如何测试缓存影响？**
A: 1) 运行基准测试（启用缓存）；2) 清除缓存；3) 再次运行；4) 对比报告。

**Q: 如何解读百分位延迟？**
A: p50 表示 50% 查询的延迟，p95 表示 95% 查询的延迟，p99 用于识别长尾延迟。

**Q: 如何持久化基准测试结果？**
A: 将 `BenchmarkResult` 列表序列化为 JSON 或写入数据库，用于历史对比。

**Q: 如何集成到 CI/CD？**
A: 在测试脚本中设置延迟阈值，超过阈值时失败：
```python
stats = benchmark.compute_stats(results)
assert stats.p95 < 200.0, f"p95 延迟过高: {stats.p95}ms"
```

---

## 相关文件清单

```
src/epip/benchmark/
├── query_benchmark.py     # 查询基准测试工具（100+ 行）
└── __init__.py            # 模块导出
```

---

## 下一步建议

- 添加吞吐量测试（QPS、TPS）
- 实现压力测试（逐步增加负载）
- 支持自定义延迟分布（正态、泊松）
- 集成性能回归检测（与历史基线对比）
- 生成可视化报告（图表、趋势）
