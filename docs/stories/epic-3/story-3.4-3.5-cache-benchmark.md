# Story 3.4: 查询缓存与性能优化

**Epic**: Epic 3 - 查询处理与多步推理
**优先级**: P1
**估算**: 中型

---

## 用户故事

**作为** 系统管理员，
**我想要** 缓存热门查询结果，
**以便** 提升重复查询的响应速度。

---

## 验收标准

### AC1: Redis 缓存集成
- [ ] 集成 Redis 缓存层
- [ ] 配置连接池
- [ ] 支持缓存序列化/反序列化
- [ ] 处理连接失败

### AC2: 查询指纹计算
- [ ] 实现查询规范化
- [ ] 计算查询哈希指纹
- [ ] 处理语义等价查询
- [ ] 支持参数化缓存键

### AC3: 缓存策略
- [ ] 实现 TTL 过期（默认 1 小时）
- [ ] 支持 LRU 淘汰
- [ ] 缓存预热机制
- [ ] 分级缓存（热/温/冷）

### AC4: 缓存指标
- [ ] 记录缓存命中率
- [ ] 记录缓存大小
- [ ] 输出 Prometheus 指标
- [ ] 提供缓存统计 API

### AC5: 缓存管理
- [ ] 提供缓存清理 API
- [ ] 支持按模式清理
- [ ] 缓存失效通知
- [ ] 手动刷新接口

---

## 技术任务

### Task 3.4.1: 查询缓存管理器
```python
# src/epip/cache/query_cache.py

@dataclass
class CacheConfig:
    redis_url: str = "redis://localhost:6379"
    default_ttl: int = 3600  # 1 hour
    max_size: int = 10000
    key_prefix: str = "epip:query:"

@dataclass
class CacheStats:
    hits: int
    misses: int
    hit_rate: float
    size: int
    memory_usage: int

class QueryCache:
    async def get(self, key: str) -> dict | None
    async def set(self, key: str, value: dict, ttl: int | None = None)
    async def delete(self, key: str)
    async def clear(self, pattern: str = "*")
    async def stats(self) -> CacheStats
```

### Task 3.4.2: 查询指纹生成器
```python
# src/epip/cache/fingerprint.py

class QueryFingerprint:
    def compute(self, query: str, params: dict | None = None) -> str
    def normalize(self, query: str) -> str
    def are_equivalent(self, q1: str, q2: str) -> bool
```

---

# Story 3.5: 查询性能基准测试

**Epic**: Epic 3 - 查询处理与多步推理
**优先级**: P2
**估算**: 小型

---

## 验收标准

### AC1: 基准测试框架
- [ ] 创建基准查询集
- [ ] 实现计时装饰器
- [ ] 支持并发测试
- [ ] 生成性能报告

### AC2: 性能指标
- [ ] 测量查询延迟（P50/P95/P99）
- [ ] 测量吞吐量（QPS）
- [ ] 对比缓存命中/未命中
- [ ] 与基线对比

---

## 技术任务

### Task 3.5.1: 性能测试器
```python
# src/epip/benchmark/query_benchmark.py

@dataclass
class BenchmarkResult:
    query: str
    latency_ms: float
    cached: bool
    success: bool

class QueryBenchmark:
    async def run(self, queries: list[str], concurrency: int = 1) -> list[BenchmarkResult]
    def report(self, results: list[BenchmarkResult]) -> str
```
