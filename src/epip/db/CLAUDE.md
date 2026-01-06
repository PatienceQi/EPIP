[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **db**

# db - 数据库客户端封装

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

提供 Neo4j 图数据库与 Redis 缓存的统一客户端封装，支持异步操作、连接管理、健康检查与优雅降级。

核心能力：
- Neo4j 图数据库 CRUD 操作（节点、关系、查询）
- Cypher 查询执行与结果转换
- Redis 连接管理与健康检查
- 可选依赖的优雅降级（无 Neo4j/Redis 时返回空实现）

---

## 入口与启动

### 主要文件

- `neo4j_client.py` - Neo4j 客户端封装
- `redis_client.py` - Redis 客户端封装

### 初始化示例

```python
from epip.db.neo4j_client import Neo4jClient
from epip.db.redis_client import RedisClient

# Neo4j 客户端
neo4j = Neo4jClient(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
neo4j.connect()

# Redis 客户端
redis = RedisClient(url="redis://localhost:6379/0")
redis.connect()

# 健康检查
is_neo4j_alive = await neo4j.ping()
is_redis_alive = await redis.ping()
```

---

## 对外接口

### Neo4jClient

**核心方法**：
- `connect()` / `close()` - 连接生命周期管理
- `run_cypher(query, parameters)` - 同步执行 Cypher 查询
- `execute_read(query, parameters)` - 异步只读查询
- `execute_write(query, parameters)` - 异步写入查询
- `ping()` - 健康检查

**节点操作**：
- `get_nodes(label, limit, offset, filters)` - 分页查询节点
- `get_node(node_id)` - 获取单个节点
- `create_node(labels, properties)` - 创建节点
- `update_node(node_id, properties)` - 更新节点属性
- `delete_node(node_id)` - 删除节点及其关系
- `search_nodes(query_text, label, limit)` - 全文搜索节点

**关系操作**：
- `get_node_relationships(node_id, direction, rel_type)` - 获取节点关系
- `create_relationship(start_id, end_id, rel_type, properties)` - 创建关系
- `delete_relationship(rel_id)` - 删除关系
- `expand_node(node_id, depth)` - 扩展节点邻居（指定深度）

**统计与元数据**：
- `get_labels()` - 获取所有节点标签
- `get_relationship_types()` - 获取所有关系类型
- `get_stats()` - 获取图统计信息（节点数、关系数、标签分布）

### RedisClient

**核心方法**：
- `connect()` / `close()` - 连接生命周期管理
- `ping()` - 健康检查

---

## 关键依赖与配置

### 依赖项

- `neo4j` - Neo4j Python 驱动（可选）
- `redis[asyncio]` - Redis 异步客户端（可选）

### 配置来源

通过环境变量或 `config.py` 传入连接参数：
- `NEO4J_URI` - Neo4j 连接地址
- `NEO4J_USER` / `NEO4J_PASSWORD` - 认证信息
- `REDIS_URL` - Redis 连接 URL

### 优雅降级策略

- 当 `neo4j` 或 `redis` 包未安装时，客户端返回空对象或空结果
- `ping()` 方法在依赖缺失时返回 `True`（假设本地开发环境）
- 所有查询方法在依赖缺失时返回空列表或 `None`

---

## 数据模型

### GraphNode

```python
@dataclass
class GraphNode:
    id: str                          # Neo4j elementId
    labels: list[str]                # 节点标签列表
    properties: dict[str, Any]       # 节点属性
```

### GraphRelationship

```python
@dataclass
class GraphRelationship:
    id: str                          # 关系 elementId
    type: str                        # 关系类型
    start_node_id: str               # 起始节点 ID
    end_node_id: str                 # 目标节点 ID
    properties: dict[str, Any]       # 关系属性
```

### GraphStats

```python
@dataclass
class GraphStats:
    node_count: int                                  # 节点总数
    relationship_count: int                          # 关系总数
    label_counts: dict[str, int]                     # 标签分布
    relationship_type_counts: dict[str, int]         # 关系类型分布
```

---

## 测试与质量

### 测试文件

- `tests/integration/test_component_integration.py` - 集成测试（Neo4j + Redis）

### 测试覆盖

- 连接管理与健康检查
- 节点 CRUD 操作
- 关系创建与查询
- 图遍历与扩展
- 优雅降级场景

---

## 常见问题 (FAQ)

**Q: 如何处理 Neo4j 连接失败？**
A: `ping()` 方法会捕获异常并返回 `False`，调用方应检查返回值并记录错误。

**Q: 为什么查询返回空列表？**
A: 可能原因：1) Neo4j 驱动未安装；2) 连接未建立；3) 查询结果为空。检查日志确认。

**Q: 如何批量创建节点？**
A: 使用 `execute_write()` 执行批量 Cypher 语句，例如 `UNWIND $batch AS item CREATE (n:Label) SET n = item`。

**Q: Redis 客户端支持哪些操作？**
A: 当前仅提供 `ping()` 健康检查，完整缓存操作由 `epip.cache` 模块封装。

---

## 相关文件清单

```
src/epip/db/
├── neo4j_client.py       # Neo4j 客户端实现（372 行）
├── redis_client.py       # Redis 客户端实现（50 行）
└── __init__.py           # 模块导出
```

---

## 下一步建议

- 补充 Neo4j 事务管理（显式事务、批量提交）
- 扩展 Redis 客户端支持基础 KV 操作
- 添加连接池配置与监控指标
- 实现 Cypher 查询构建器（类型安全）
