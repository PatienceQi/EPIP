# Story 3.3: ReAct 多步推理循环

**Epic**: Epic 3 - 查询处理与多步推理
**优先级**: P0
**估算**: 大型

---

## 用户故事

**作为** 终端用户，
**我想要** 系统能进行多步推理，
**以便** 回答复杂的关联查询（如影响链分析）。

---

## 验收标准

### AC1: ReAct 框架实现
- [ ] 实现 Reason → Act → Observe 循环
- [ ] 支持最多 5 轮迭代
- [ ] 每轮生成推理步骤说明
- [ ] 检测循环终止条件

### AC2: 查询分解
- [ ] 将复杂查询分解为 3-5 个子查询
- [ ] 子查询间建立依赖关系
- [ ] 支持并行执行独立子查询
- [ ] 动态调整分解策略

### AC3: 子查询执行
- [ ] 每个子查询独立执行路径搜索
- [ ] 收集中间结果
- [ ] 处理子查询失败情况
- [ ] 记录执行轨迹

### AC4: 结果聚合
- [ ] 聚合多分支查询结果
- [ ] 基于置信度和路径长度排名
- [ ] 去重和合并相似结果
- [ ] 生成最终答案

### AC5: 推理日志
- [ ] 输出完整推理过程日志
- [ ] 包含每步的输入/输出
- [ ] 记录决策依据
- [ ] 支持调试和审计

---

## 技术任务

### Task 3.3.1: ReAct 核心框架
```python
# src/epip/reasoning/react.py

from dataclasses import dataclass
from enum import Enum

class ActionType(Enum):
    SEARCH = "search"       # 搜索实体
    TRAVERSE = "traverse"   # 遍历关系
    AGGREGATE = "aggregate" # 聚合结果
    CONCLUDE = "conclude"   # 得出结论

@dataclass
class Thought:
    """推理思考"""
    step: int
    reasoning: str
    action: ActionType
    action_input: dict

@dataclass
class Observation:
    """观察结果"""
    step: int
    result: dict
    success: bool
    error: str | None = None

@dataclass
class ReActTrace:
    """完整推理轨迹"""
    query: str
    thoughts: list[Thought]
    observations: list[Observation]
    final_answer: str
    confidence: float
    total_steps: int

class ReActAgent:
    """ReAct 推理代理"""

    def __init__(
        self,
        kg_builder: KGBuilder,
        llm_backend: LLMBackend,
        max_iterations: int = 5
    ):
        pass

    async def reason(self, query: str) -> ReActTrace:
        """执行 ReAct 推理循环"""
        pass

    async def _think(self, query: str, history: list) -> Thought:
        """生成思考和行动"""
        pass

    async def _act(self, thought: Thought) -> Observation:
        """执行行动"""
        pass

    def _should_terminate(self, thought: Thought, iterations: int) -> bool:
        """检查是否应该终止"""
        pass
```

### Task 3.3.2: 查询分解器
```python
# src/epip/reasoning/decomposer.py

@dataclass
class SubQuery:
    """子查询"""
    id: str
    question: str
    depends_on: list[str]
    priority: int

@dataclass
class DecomposedQuery:
    """分解后的查询"""
    original: str
    sub_queries: list[SubQuery]
    execution_order: list[list[str]]  # 分层执行顺序

class QueryDecomposer:
    """查询分解器"""

    async def decompose(self, query: str) -> DecomposedQuery:
        """将复杂查询分解为子查询"""
        pass

    def build_execution_plan(self, sub_queries: list[SubQuery]) -> list[list[str]]:
        """构建执行计划（拓扑排序）"""
        pass
```

### Task 3.3.3: 结果聚合器
```python
# src/epip/reasoning/aggregator.py

@dataclass
class RankedResult:
    """排名后的结果"""
    content: str
    confidence: float
    path_length: int
    source_queries: list[str]

class ResultAggregator:
    """结果聚合器"""

    def aggregate(
        self,
        results: list[dict],
        strategy: str = "confidence"
    ) -> list[RankedResult]:
        """聚合多个查询结果"""
        pass

    def deduplicate(self, results: list[RankedResult]) -> list[RankedResult]:
        """去重相似结果"""
        pass

    def rank(
        self,
        results: list[RankedResult],
        weights: dict[str, float] | None = None
    ) -> list[RankedResult]:
        """排名结果"""
        pass
```

---

## 测试用例

### 单元测试
- [ ] 测试 `_think()` 思考生成
- [ ] 测试 `_act()` 行动执行
- [ ] 测试 `decompose()` 查询分解
- [ ] 测试 `aggregate()` 结果聚合
- [ ] 测试终止条件检测

### 集成测试
- [ ] 测试完整 ReAct 循环
- [ ] 测试多步推理（3-5 步）
- [ ] 测试子查询并行执行

### 验收测试
- [ ] 正确回答复杂关联查询
- [ ] 推理步骤清晰可解释
- [ ] 平均推理轮次 ≤3

---

## 依赖关系

- **前置**: Story 3.2（需要 Cypher 执行器）
- **后置**: Story 3.4（缓存推理结果）
