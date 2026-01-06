[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **cache**

# cache - 查询缓存与指纹计算

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

提供 Redis 支持的查询缓存层，支持优雅降级到内存缓存，并提供查询指纹计算能力。

核心能力：
- Redis 查询缓存（带 TTL）
- 内存缓存回退（LRU 策略）
- 查询指纹计算（语义等价性检测）
- 缓存统计（命中率、内存使用）
- 模式匹配清除

---

## 入口与启动

### 主要文件

- `query_cache.py` - 查询缓存实现
- `fingerprint.py` - 查询指纹计算

### 初始化示例

```python
from epip.cache.query_cache import QueryCache, CacheConfig, CacheStats
from epip.cache.fingerprint import QueryFingerprint

# 配置缓存
config = CacheConfig(
    redis_url="redis://localhost:6379/0",
    default_ttl=3600,
    max_size=10_000,
    key_prefix="epip:query:"
)

# 初始化缓存
cache = QueryCache(config=config)
await cache.connect()

# 查询指纹计算
fingerprint = QueryFingerprint()
key = fingerprint.compute("2023年女性创业政策")

# 缓存操作
await cache.set(key, {"result": "..."}, ttl=1800)
result = await cache.get(key)

# 缓存统计
stats = await cache.stats()
print(f"命中率: {stats.hit_rate:.2%}")

# 清除缓存
await cache.clear(pattern="epip:query:2023*")
```

---

## 对外接口

### QueryCache

**核心方法**：
- `connect()` - 连接 Redis（自动降级）
- `close()` - 关闭连接
- `get(key: str) -> CacheValue | None` - 获取缓存
- `set(key: str, value: CacheValue, ttl: int | None)` - 设置缓存
- `delete(key: str) -> bool` - 删除缓存
- `clear(pattern: str | None) -> int` - 清除缓存（支持模式匹配）
- `stats() -> CacheStats` - 获取缓存统计

### CacheConfig

```python
@dataclass
class CacheConfig:
    redis_url: str                           # Redis 连接 URL
    default_ttl: int                         # 默认 TTL（秒，默认 3600）
    max_size: int                            # 最大缓存条目数（默认 10,000）
    key_prefix: str                          # 键前缀（默认 "epip:query:"）
```

### CacheStats

```python
@dataclass
class CacheStats:
    hits: int                                # 命中次数
    misses: int                              # 未命中次数
    hit_rate: float                          # 命中率（0-1）
    size: int                                # 当前缓存条目数
    memory_usage: int                        # 内存使用（字节）
```

### QueryFingerprint

**核心方法**：
- `compute(query: str) -> str` - 计算查询指纹（SHA256）
- `normalize(query: str) -> str` - 查询规范化（去空格、小写、排序参数）

---

## 关键依赖与配置

### 依赖项

- `redis[asyncio]` - Redis 异步客户端（可选）
- `hashlib` - 哈希计算（Python 标准库）

### 配置参数

- `redis_url` - Redis 连接地址
- `default_ttl` - 默认过期时间（秒）
- `max_size` - 内存缓存最大条目数
- `key_prefix` - 键命名空间前缀

### 优雅降级策略

1. **Redis 不可用时**：
   - 自动切换到内存缓存（`OrderedDict`）
   - 使用 LRU 策略淘汰旧条目
   - 保持相同的 API 接口

2. **内存缓存限制**：
   - 达到 `max_size` 时删除最旧条目
   - TTL 通过时间戳检查实现

---

## 数据模型

### 缓存键结构

```
{key_prefix}{fingerprint}
例如：epip:query:a3f5e8d9c2b1...
```

### 缓存值结构

```python
CacheValue = dict[str, Any]

# 示例
{
    "query": "2023年女性创业政策",
    "result": [...],
    "metadata": {
        "timestamp": "2026-01-06T19:49:12+0800",
        "execution_time_ms": 123.45
    }
}
```

### 指纹计算流程

```
原始查询
    ↓
规范化（去空格、小写、排序）
    ↓
SHA256 哈希
    ↓
十六进制字符串（64 字符）
```

---

## 测试与质量

### 测试文件

- `tests/unit/test_query_cache.py` - 单元测试（缓存操作、降级、统计）

### 测试覆盖

- Redis 缓存读写
- 内存缓存回退
- TTL 过期处理
- 模式匹配清除
- 指纹计算一致性
- 并发访问安全性
- 统计数据准确性

---

## 常见问题 (FAQ)

**Q: 如何提高缓存命中率？**
A: 1) 优化查询指纹计算（语义等价性）；2) 调整 TTL 策略；3) 预热常见查询。

**Q: Redis 连接失败怎么办？**
A: 系统会自动降级到内存缓存，不影响功能，但缓存不跨进程共享。

**Q: 如何清除特定租户的缓存？**
A: 使用模式匹配：`await cache.clear(pattern="epip:query:tenant-001:*")`。

**Q: 内存缓存会占用多少内存？**
A: 取决于 `max_size` 和单条缓存大小，建议监控 `CacheStats.memory_usage`。

**Q: 如何实现缓存预热？**
A: 在系统启动时批量执行常见查询并缓存结果。

**Q: 指纹计算如何处理语义等价查询？**
A: 当前基于字符串规范化，未来可集成语义相似度模型（Sentence-BERT）。

---

## 相关文件清单

```
src/epip/cache/
├── query_cache.py         # 查询缓存实现（100+ 行）
├── fingerprint.py         # 查询指纹计算
└── __init__.py            # 模块导出
```

---

## 下一步建议

- 实现语义相似度缓存（Sentence-BERT）
- 添加缓存预热策略（启动时加载热点查询）
- 支持缓存分层（L1 内存 + L2 Redis）
- 集成缓存监控指标（Prometheus）
- 实现缓存失效策略（主动失效、依赖失效）
