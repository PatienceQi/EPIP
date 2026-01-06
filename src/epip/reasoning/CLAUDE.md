[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **reasoning**

# reasoning - ReAct 推理引擎

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

实现 ReAct（Reason-Act-Observe）推理循环，支持复杂查询分解、多步推理、结果聚合与排序。

核心能力：
- ReAct 推理循环（思考 → 行动 → 观察 → 结论）
- 复杂查询分解（子问题拆分）
- 多步推理轨迹记录
- 结果聚合与排序
- 置信度评估

---

## 入口与启动

### 主要文件

- `react.py` - ReAct 推理代理实现
- `decomposer.py` - 查询分解器
- `aggregator.py` - 结果聚合器

### 初始化示例

```python
from epip.reasoning.react import ReActAgent
from epip.reasoning.decomposer import QueryDecomposer
from epip.reasoning.aggregator import ResultAggregator
from epip.core.kg_builder import KnowledgeGraphBuilder
from epip.core.llm_backend import create_llm_backend
from epip.config import ReActSettings

# 初始化组件
kg_builder = KnowledgeGraphBuilder(...)
llm_backend = create_llm_backend(config)
decomposer = QueryDecomposer()
aggregator = ResultAggregator()

# 创建 ReAct 代理
settings = ReActSettings(
    max_iterations=5,
    timeout_per_step=30.0
)
agent = ReActAgent(
    kg_builder=kg_builder,
    llm_backend=llm_backend,
    decomposer=decomposer,
    aggregator=aggregator,
    settings=settings
)

# 执行推理
trace = await agent.reason("比较2022年和2023年女性创业政策的差异")
print(f"最终答案: {trace.final_answer}")
print(f"置信度: {trace.confidence}")
print(f"推理步数: {trace.total_steps}")
```

---

## 对外接口

### ReActAgent

**核心方法**：
- `reason(query: str) -> ReActTrace` - 执行完整推理循环

**支持的动作类型**：
- `SEARCH` - 搜索知识图谱
- `TRAVERSE` - 遍历图结构
- `AGGREGATE` - 聚合统计
- `CONCLUDE` - 得出结论

### ReActTrace

```python
@dataclass
class ReActTrace:
    query: str                      # 原始查询
    thoughts: list[Thought]         # 思考步骤列表
    observations: list[Observation] # 观察结果列表
    final_answer: str               # 最终答案
    confidence: float               # 置信度（0-1）
    total_steps: int                # 总步数
```

### Thought

```python
@dataclass
class Thought:
    step: int                       # 步骤编号
    reasoning: str                  # 推理过程
    action: ActionType              # 下一步动作
    action_input: dict[str, Any]    # 动作参数
```

### Observation

```python
@dataclass
class Observation:
    step: int                       # 步骤编号
    result: dict[str, Any]          # 执行结果
    success: bool                   # 是否成功
    error: str | None               # 错误信息
```

### QueryDecomposer

**核心方法**：
- `decompose(query: str) -> DecomposedQuery` - 分解复杂查询

### ResultAggregator

**核心方法**：
- `aggregate(results: list[dict]) -> list[RankedResult]` - 聚合与排序结果

---

## 关键依赖与配置

### 依赖项

- `epip.core.kg_builder` - 知识图谱构建器
- `epip.core.llm_backend` - LLM 后端
- `epip.config` - 配置管理
- `structlog` - 结构化日志

### 配置参数（ReActSettings）

- `max_iterations` - 最大推理步数（默认 5）
- `timeout_per_step` - 单步超时时间（秒，默认 30.0）

### 推理循环流程

1. **查询分解**：将复杂查询拆分为子问题
2. **思考阶段**：LLM 生成推理过程与下一步动作
3. **行动阶段**：执行动作（搜索、遍历、聚合）
4. **观察阶段**：记录执行结果
5. **循环判断**：
   - 达到最大步数 → 强制结束
   - 动作为 CONCLUDE → 输出结论
   - 否则继续下一轮
6. **结果聚合**：合并多步结果，计算置信度

---

## 数据模型

### 推理轨迹结构

```
ReActTrace
├── query: "原始查询"
├── thoughts: [
│   ├── Thought(step=1, reasoning="...", action=SEARCH, ...)
│   ├── Thought(step=2, reasoning="...", action=TRAVERSE, ...)
│   └── Thought(step=3, reasoning="...", action=CONCLUDE, ...)
│   ]
├── observations: [
│   ├── Observation(step=1, result={...}, success=True)
│   ├── Observation(step=2, result={...}, success=True)
│   └── Observation(step=3, result={...}, success=True)
│   ]
├── final_answer: "最终答案"
├── confidence: 0.85
└── total_steps: 3
```

---

## 测试与质量

### 测试文件

- `tests/unit/test_react_reasoning.py` - 单元测试（推理循环、分解、聚合）

### 测试覆盖

- 单步推理执行
- 多步推理循环
- 查询分解准确性
- 结果聚合与排序
- 超时与异常处理
- 置信度计算

---

## 常见问题 (FAQ)

**Q: 推理循环何时终止？**
A: 满足以下任一条件：1) 达到最大步数；2) 动作为 CONCLUDE；3) 发生不可恢复错误。

**Q: 如何调整推理深度？**
A: 修改 `ReActSettings.max_iterations`，建议范围 3-10 步。

**Q: 置信度如何计算？**
A: 基于以下因素：1) 成功步数占比；2) 结果一致性；3) 证据强度。具体算法见 `aggregator.py`。

**Q: 如何调试推理过程？**
A: 访问 `/api/visualization/trace/{trace_id}` 查看完整推理轨迹，或启用 DEBUG 日志。

**Q: 查询分解失败怎么办？**
A: 分解器会捕获异常并记录警告，推理循环会继续执行（视为单步查询）。

---

## 相关文件清单

```
src/epip/reasoning/
├── react.py           # ReAct 推理代理（100+ 行）
├── decomposer.py      # 查询分解器
├── aggregator.py      # 结果聚合器
└── __init__.py        # 模块导出
```

---

## 下一步建议

- 补充推理策略配置（贪心、束搜索）
- 实现推理缓存（相似查询复用）
- 扩展动作类型（FILTER、SORT、JOIN）
- 添加推理轨迹可视化（前端集成）
- 优化置信度计算算法
