# Story 3.1: 自然语言查询解析

**Epic**: Epic 3 - 查询处理与多步推理
**优先级**: P0
**估算**: 中型

---

## 用户故事

**作为** 终端用户，
**我想要** 用自然语言提问，
**以便** 无需学习 Cypher 即可查询知识图谱。

---

## 验收标准

### AC1: 查询输入接口
- [ ] 实现 CLI 查询命令 `epip query "问题"`
- [ ] 实现 REST API `/api/query` 端点
- [ ] 支持中英文查询输入
- [ ] 查询历史记录

### AC2: 查询意图解析
- [ ] 使用 LLM 解析自然语言查询
- [ ] 提取查询中的中心实体
- [ ] 识别查询意图类型（事实查询/关系查询/聚合查询）
- [ ] 提取时间、地点等约束条件

### AC3: 查询计划生成
- [ ] 将解析结果转为结构化查询计划
- [ ] 输出 JSON 格式查询计划
- [ ] 支持多步查询分解
- [ ] 估算查询复杂度

### AC4: 实体链接
- [ ] 将查询中的实体名链接到 KG 节点
- [ ] 处理实体别名和模糊匹配
- [ ] 返回候选实体列表及置信度

### AC5: 查询验证
- [ ] 验证查询计划可执行性
- [ ] 检测无法解析的查询
- [ ] 提供查询建议和纠错

---

## 技术任务

### Task 3.1.1: 查询解析器
```python
# src/epip/query/parser.py

from dataclasses import dataclass
from enum import Enum

class QueryIntent(Enum):
    FACT = "fact"           # 事实查询：某实体的属性
    RELATION = "relation"   # 关系查询：实体间关系
    PATH = "path"           # 路径查询：两实体间路径
    AGGREGATE = "aggregate" # 聚合查询：统计分析
    COMPARE = "compare"     # 比较查询：多实体对比

@dataclass
class EntityMention:
    """查询中提到的实体"""
    text: str               # 原始文本
    entity_type: str | None # 推断类型
    start: int              # 起始位置
    end: int                # 结束位置

@dataclass
class QueryConstraint:
    """查询约束条件"""
    field: str              # 约束字段（time, location, etc）
    operator: str           # 操作符（=, >, <, between）
    value: str | list       # 约束值

@dataclass
class ParsedQuery:
    """解析后的查询"""
    original: str
    intent: QueryIntent
    entities: list[EntityMention]
    constraints: list[QueryConstraint]
    complexity: int         # 1-5 复杂度评估

class QueryParser:
    """自然语言查询解析器"""

    async def parse(self, query: str) -> ParsedQuery:
        """解析自然语言查询"""
        pass

    async def extract_entities(self, query: str) -> list[EntityMention]:
        """提取查询中的实体提及"""
        pass

    async def classify_intent(self, query: str) -> QueryIntent:
        """分类查询意图"""
        pass
```

### Task 3.1.2: 实体链接器
```python
# src/epip/query/linker.py

@dataclass
class LinkedEntity:
    """链接后的实体"""
    mention: EntityMention
    kg_node_id: str
    kg_node_name: str
    confidence: float
    alternatives: list[tuple[str, float]]  # 候选实体

class EntityLinker:
    """实体链接器"""

    async def link(
        self,
        mentions: list[EntityMention],
        kg_builder: KGBuilder
    ) -> list[LinkedEntity]:
        """将实体提及链接到 KG 节点"""
        pass

    async def fuzzy_match(
        self,
        text: str,
        candidates: list[str],
        threshold: float = 0.7
    ) -> list[tuple[str, float]]:
        """模糊匹配实体"""
        pass
```

### Task 3.1.3: 查询计划生成器
```python
# src/epip/query/planner.py

@dataclass
class QueryStep:
    """查询步骤"""
    step_id: int
    action: str             # search, traverse, filter, aggregate
    params: dict
    depends_on: list[int]   # 依赖的步骤

@dataclass
class QueryPlan:
    """查询执行计划"""
    query_id: str
    parsed: ParsedQuery
    linked_entities: list[LinkedEntity]
    steps: list[QueryStep]
    estimated_cost: float

class QueryPlanner:
    """查询计划生成器"""

    async def plan(
        self,
        parsed: ParsedQuery,
        linked: list[LinkedEntity]
    ) -> QueryPlan:
        """生成查询执行计划"""
        pass

    def validate_plan(self, plan: QueryPlan) -> list[str]:
        """验证计划可执行性"""
        pass

    def to_json(self, plan: QueryPlan) -> str:
        """导出 JSON 格式"""
        pass
```

### Task 3.1.4: CLI 和 API 集成
```python
# scripts/query_cli.py - CLI 入口
# src/epip/api/routes.py - 更新 API 路由
```

---

## 测试用例

### 单元测试
- [ ] 测试 `classify_intent()` 意图分类
- [ ] 测试 `extract_entities()` 实体提取
- [ ] 测试 `link()` 实体链接
- [ ] 测试 `plan()` 计划生成
- [ ] 测试中英文查询解析

### 集成测试
- [ ] 测试完整查询解析流程
- [ ] 测试 CLI 命令
- [ ] 测试 API 端点

### 验收测试
- [ ] 正确解析 10 个典型查询
- [ ] 实体链接准确率 >85%
- [ ] 查询计划有效率 >90%

---

## 依赖关系

- **前置**: Epic 2（需要高质量 KG）
- **后置**: Story 3.2（Cypher 执行需要查询计划）

---

## 相关文档

- 架构: `docs/architecture.md`
- KG: `src/epip/core/kg_builder.py`
- 实体: `src/epip/core/entity_extractor.py`
