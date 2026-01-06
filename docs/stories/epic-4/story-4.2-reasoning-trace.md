# Story 4.2: 推理路径追踪

**Epic**: Epic 4 - 幻觉检测与可追溯性
**优先级**: P0
**估算**: 中型

---

## 用户故事

**作为** 终端用户，
**我想要** 查看每个答案的推理路径，
**以便** 理解系统是如何得出结论的。

---

## 验收标准

### AC1: 路径记录
- [ ] 记录完整推理步骤
- [ ] 每步包含输入/输出/置信度
- [ ] 标记关键节点
- [ ] 记录决策依据

### AC2: 路径分析
- [ ] 计算路径长度
- [ ] 识别关键分支点
- [ ] 检测推理弱点
- [ ] 评估路径质量

### AC3: 路径可视化数据
- [ ] 生成节点列表
- [ ] 生成边列表
- [ ] 标注节点类型和置信度
- [ ] 支持多级展开

### AC4: 溯源信息
- [ ] 每个结论关联源节点
- [ ] 提供 KG 节点引用
- [ ] 支持反向追溯
- [ ] 记录推理链条

---

## 技术任务

### Task 4.2.1: 推理轨迹记录器
```python
# src/epip/verification/trace.py

from dataclasses import dataclass
from datetime import datetime

@dataclass
class TraceNode:
    """推理节点"""
    node_id: str
    node_type: str  # "thought", "action", "observation", "conclusion"
    content: str
    confidence: float
    timestamp: datetime
    kg_references: list[str]  # 关联的 KG 节点 ID
    metadata: dict

@dataclass
class TraceEdge:
    """推理边"""
    source_id: str
    target_id: str
    edge_type: str  # "leads_to", "supports", "contradicts"
    weight: float

@dataclass
class ReasoningTrace:
    """完整推理轨迹"""
    trace_id: str
    query: str
    nodes: list[TraceNode]
    edges: list[TraceEdge]
    critical_path: list[str]  # 关键路径节点 ID
    total_steps: int
    avg_confidence: float

class TraceRecorder:
    """轨迹记录器"""

    def __init__(self):
        self._nodes: list[TraceNode] = []
        self._edges: list[TraceEdge] = []

    def record_node(
        self,
        node_type: str,
        content: str,
        confidence: float,
        kg_refs: list[str] | None = None
    ) -> str:
        """记录节点"""
        pass

    def record_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0
    ) -> None:
        """记录边"""
        pass

    def build_trace(self, query: str) -> ReasoningTrace:
        """构建完整轨迹"""
        pass

    def find_critical_path(self) -> list[str]:
        """找到关键路径"""
        pass
```

### Task 4.2.2: 路径分析器
```python
# src/epip/verification/path_analyzer.py

from dataclasses import dataclass

@dataclass
class PathAnalysis:
    """路径分析结果"""
    path_length: int
    branch_points: list[str]
    weak_points: list[str]  # 低置信度节点
    quality_score: float
    bottlenecks: list[str]

class PathAnalyzer:
    """路径分析器"""

    def analyze(self, trace: ReasoningTrace) -> PathAnalysis:
        """分析推理路径"""
        pass

    def find_weak_points(
        self,
        trace: ReasoningTrace,
        threshold: float = 0.7
    ) -> list[str]:
        """找到推理弱点"""
        pass

    def calculate_quality(self, trace: ReasoningTrace) -> float:
        """计算路径质量分数"""
        pass

    def suggest_improvements(self, analysis: PathAnalysis) -> list[str]:
        """建议改进"""
        pass
```

### Task 4.2.3: 溯源服务
```python
# src/epip/verification/provenance.py

from dataclasses import dataclass

@dataclass
class ProvenanceInfo:
    """溯源信息"""
    conclusion: str
    source_nodes: list[str]
    reasoning_chain: list[str]
    confidence: float
    evidence_count: int

class ProvenanceService:
    """溯源服务"""

    def __init__(self, kg_client):
        pass

    async def trace_back(
        self,
        conclusion_node_id: str,
        trace: ReasoningTrace
    ) -> ProvenanceInfo:
        """反向追溯"""
        pass

    async def get_kg_context(self, node_ids: list[str]) -> dict:
        """获取 KG 上下文"""
        pass

    def build_reasoning_chain(
        self,
        trace: ReasoningTrace,
        target_node: str
    ) -> list[str]:
        """构建推理链条"""
        pass
```

---

## 测试用例

### 单元测试
- [ ] 测试 `record_node()` 节点记录
- [ ] 测试 `find_critical_path()` 关键路径
- [ ] 测试 `find_weak_points()` 弱点检测
- [ ] 测试 `trace_back()` 反向追溯

### 集成测试
- [ ] 测试完整轨迹记录
- [ ] 测试路径分析流程

---

## 依赖关系

- **前置**: Story 4.1（事实验证结果）
- **后置**: Story 4.3（可视化展示）
