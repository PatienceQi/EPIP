# Story 4.3: 可视化展示

**Epic**: Epic 4 - 幻觉检测与可追溯性
**优先级**: P1
**估算**: 中型

---

## 用户故事

**作为** 终端用户，
**我想要** 通过可视化界面查看推理过程和验证结果，
**以便** 直观理解答案的可信度。

---

## 验收标准

### AC1: 推理路径可视化
- [ ] 使用 D3.js 力导向图展示节点
- [ ] 不同节点类型使用不同颜色
- [ ] 边显示权重和类型
- [ ] 支持节点点击展开详情

### AC2: 置信度热力图
- [ ] 按置信度着色节点
- [ ] 高置信度绿色，低置信度红色
- [ ] 支持阈值筛选
- [ ] 显示置信度分布

### AC3: 证据面板
- [ ] 点击节点显示证据列表
- [ ] 显示证据来源和内容
- [ ] 支持跳转到 KG 节点
- [ ] 显示冲突标记

### AC4: 导出功能
- [ ] 导出 SVG 图片
- [ ] 导出 JSON 数据
- [ ] 导出 Markdown 报告
- [ ] 支持分享链接

---

## 技术任务

### Task 4.3.1: 可视化数据生成器
```python
# src/epip/visualization/data_generator.py

from dataclasses import dataclass

@dataclass
class VisNode:
    """可视化节点"""
    id: str
    label: str
    type: str
    confidence: float
    color: str
    size: int
    metadata: dict

@dataclass
class VisEdge:
    """可视化边"""
    source: str
    target: str
    label: str
    weight: float
    color: str

@dataclass
class VisGraph:
    """可视化图数据"""
    nodes: list[VisNode]
    edges: list[VisEdge]
    layout: str = "force"

class VisualizationDataGenerator:
    """可视化数据生成器"""

    def from_trace(self, trace: ReasoningTrace) -> VisGraph:
        """从推理轨迹生成可视化数据"""
        pass

    def from_verification(self, report: VerificationReport) -> VisGraph:
        """从验证报告生成可视化数据"""
        pass

    def _confidence_to_color(self, confidence: float) -> str:
        """置信度转颜色"""
        pass

    def _node_type_to_color(self, node_type: str) -> str:
        """节点类型转颜色"""
        pass

    def to_d3_json(self, graph: VisGraph) -> dict:
        """转换为 D3.js 兼容格式"""
        pass
```

### Task 4.3.2: API 端点
```python
# src/epip/api/visualization.py

from fastapi import APIRouter

router = APIRouter(prefix="/api/visualization", tags=["visualization"])

@router.get("/trace/{trace_id}")
async def get_trace_visualization(trace_id: str) -> dict:
    """获取推理轨迹可视化数据"""
    pass

@router.get("/verification/{answer_id}")
async def get_verification_visualization(answer_id: str) -> dict:
    """获取验证结果可视化数据"""
    pass

@router.get("/evidence/{node_id}")
async def get_node_evidence(node_id: str) -> dict:
    """获取节点证据详情"""
    pass

@router.post("/export")
async def export_visualization(
    graph: VisGraph,
    format: str = "json"
) -> dict:
    """导出可视化数据"""
    pass
```

### Task 4.3.3: 前端组件（React + D3）
```typescript
// 仅提供接口规范，前端实现独立
interface TraceVisualizerProps {
  traceId: string;
  onNodeClick: (nodeId: string) => void;
  showConfidence: boolean;
  filterThreshold: number;
}

interface EvidencePanelProps {
  nodeId: string;
  evidences: Evidence[];
  onNavigateToKG: (kgNodeId: string) => void;
}
```

---

## 测试用例

### 单元测试
- [ ] 测试 `from_trace()` 数据生成
- [ ] 测试 `_confidence_to_color()` 颜色映射
- [ ] 测试 `to_d3_json()` 格式转换

### API 测试
- [ ] 测试 `/trace/{trace_id}` 端点
- [ ] 测试 `/verification/{answer_id}` 端点
- [ ] 测试 `/export` 端点

---

## 依赖关系

- **前置**: Story 4.2（推理轨迹数据）
- **后置**: 无
