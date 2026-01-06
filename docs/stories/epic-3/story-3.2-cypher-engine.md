# Story 3.2: Cypher 查询执行引擎

**Epic**: Epic 3 - 查询处理与多步推理
**优先级**: P0
**估算**: 中型

---

## 用户故事

**作为** 系统，
**我想要** 高效执行 Cypher 图查询，
**以便** 快速检索知识图谱数据。

---

## 验收标准

### AC1: Cypher 查询生成
- [ ] 从 QueryPlan 生成 Cypher 查询语句
- [ ] 支持节点匹配（MATCH）
- [ ] 支持关系遍历
- [ ] 支持属性过滤（WHERE）
- [ ] 支持结果限制（LIMIT）

### AC2: 路径搜索算法
- [ ] 集成 Neo4j GDS 的 A* 算法
- [ ] 集成 Dijkstra 最短路径算法
- [ ] 支持加权路径搜索
- [ ] 支持多跳路径查询

### AC3: 查询优化
- [ ] 实现查询预处理（参数化）
- [ ] 剪枝无关子图（相似度 >0.7）
- [ ] 查询计划缓存
- [ ] 批量查询优化

### AC4: 超时与回退
- [ ] 实现查询超时机制（可配置，默认 30 秒）
- [ ] 超时后回退到简化查询
- [ ] 记录超时查询供分析

### AC5: 结果处理
- [ ] 将 Cypher 结果转为结构化对象
- [ ] 提取节点和关系信息
- [ ] 计算结果置信度
- [ ] 支持分页返回

---

## 技术任务

### Task 3.2.1: Cypher 生成器
```python
# src/epip/query/cypher.py

from dataclasses import dataclass

@dataclass
class CypherQuery:
    """Cypher 查询"""
    statement: str
    parameters: dict
    timeout: float
    fallback: str | None = None

class CypherGenerator:
    """Cypher 查询生成器"""

    def from_plan(self, plan: QueryPlan) -> CypherQuery:
        """从查询计划生成 Cypher"""
        pass

    def match_node(self, entity: LinkedEntity) -> str:
        """生成节点匹配子句"""
        pass

    def traverse_relation(
        self, source: str, target: str, rel_type: str | None = None
    ) -> str:
        """生成关系遍历子句"""
        pass

    def path_query(
        self, start: str, end: str, max_hops: int = 5
    ) -> str:
        """生成路径查询"""
        pass
```

### Task 3.2.2: 查询执行器
```python
# src/epip/query/executor.py

@dataclass
class QueryResult:
    """查询结果"""
    nodes: list[dict]
    relations: list[dict]
    paths: list[list[dict]]
    execution_time: float
    timed_out: bool = False

class CypherExecutor:
    """Cypher 查询执行器"""

    def __init__(self, neo4j_driver, timeout: float = 30.0):
        self.driver = neo4j_driver
        self.timeout = timeout

    async def execute(self, query: CypherQuery) -> QueryResult:
        """执行 Cypher 查询"""
        pass

    async def execute_with_fallback(self, query: CypherQuery) -> QueryResult:
        """执行查询，超时则回退"""
        pass

    async def shortest_path(
        self, start_id: str, end_id: str, algorithm: str = "dijkstra"
    ) -> list[dict]:
        """执行最短路径查询"""
        pass
```

### Task 3.2.3: 路径算法集成
```python
# src/epip/query/algorithms.py

class PathAlgorithms:
    """路径搜索算法"""

    async def dijkstra(
        self, driver, start: str, end: str, weight_property: str = "weight"
    ) -> list[dict]:
        """Dijkstra 最短路径"""
        pass

    async def astar(
        self, driver, start: str, end: str, heuristic: str = "haversine"
    ) -> list[dict]:
        """A* 路径搜索"""
        pass

    async def all_shortest_paths(
        self, driver, start: str, end: str, max_paths: int = 10
    ) -> list[list[dict]]:
        """所有最短路径"""
        pass
```

---

## 测试用例

### 单元测试
- [ ] 测试 `from_plan()` Cypher 生成
- [ ] 测试 `match_node()` 节点匹配
- [ ] 测试 `path_query()` 路径查询
- [ ] 测试超时回退机制

### 集成测试
- [ ] 测试完整查询执行流程
- [ ] 测试路径算法（mock Neo4j）
- [ ] 测试结果解析

### 验收测试
- [ ] 查询响应时间 <5s（简单查询）
- [ ] 超时机制正确触发
- [ ] 路径查询结果正确

---

## 依赖关系

- **前置**: Story 3.1（需要 QueryPlan）
- **后置**: Story 3.3（ReAct 需要执行引擎）
