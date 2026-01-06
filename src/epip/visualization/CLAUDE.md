[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **visualization**

# visualization - 可视化数据生成

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

将知识图谱、推理轨迹、验证报告转换为前端可视化组件（D3.js）所需的数据格式。

核心能力：
- 推理轨迹转图结构（节点、边、布局）
- 验证报告转可视化数据
- 节点着色与大小计算（基于置信度、类型）
- 关键路径高亮
- 元数据序列化

---

## 入口与启动

### 主要文件

- `data_generator.py` - 可视化数据生成器

### 初始化示例

```python
from epip.visualization.data_generator import VisualizationDataGenerator
from epip.verification.trace import ReasoningTrace
from epip.verification.report import VerificationReport

# 初始化生成器
generator = VisualizationDataGenerator(base_node_size=26)

# 从推理轨迹生成图数据
trace = ReasoningTrace(...)
vis_graph = generator.from_trace(trace)

# 从验证报告生成图数据
report = VerificationReport(...)
vis_graph = generator.from_report(report)

# 输出 JSON（供前端使用）
import json
json_data = json.dumps({
    "nodes": [node.__dict__ for node in vis_graph.nodes],
    "edges": [edge.__dict__ for edge in vis_graph.edges],
    "layout": vis_graph.layout
})
```

---

## 对外接口

### VisualizationDataGenerator

**核心方法**：
- `from_trace(trace: ReasoningTrace) -> VisGraph` - 从推理轨迹生成图
- `from_report(report: VerificationReport) -> VisGraph` - 从验证报告生成图

### VisGraph

```python
@dataclass
class VisGraph:
    nodes: list[VisNode]                     # 节点列表
    edges: list[VisEdge]                     # 边列表
    layout: str                              # 布局算法（force、hierarchical、circular）
```

### VisNode

```python
@dataclass
class VisNode:
    id: str                                  # 节点 ID
    label: str                               # 显示标签
    type: str                                # 节点类型（thought、action、observation、fact、evidence）
    confidence: float                        # 置信度（0-1）
    color: str                               # 节点颜色（十六进制）
    size: int                                # 节点大小（像素）
    metadata: dict[str, Any]                 # 元数据（时间戳、KG 引用等）
```

### VisEdge

```python
@dataclass
class VisEdge:
    source: str                              # 起始节点 ID
    target: str                              # 目标节点 ID
    label: str                               # 边标签
    weight: float                            # 边权重
    color: str                               # 边颜色（十六进制）
```

---

## 关键依赖与配置

### 依赖项

- `epip.verification.trace` - 推理轨迹数据结构
- `epip.verification.report` - 验证报告数据结构

### 配置参数

- `base_node_size` - 基础节点大小（默认 26 像素）

### 颜色方案

**节点类型颜色**：
- `thought` - 深蓝色 `#3949ab`
- `action` - 青色 `#00838f`
- `observation` - 紫色 `#6a1b9a`
- `conclusion` - 橙色 `#ef6c00`
- `answer` - 深蓝 `#283593`
- `fact` - 蓝色 `#0277bd`
- `evidence` - 灰蓝 `#455a64`
- `conflict` - 红色 `#b71c1c`

**边类型颜色**：
- `supports` - 绿色 `#2e7d32`
- `leads_to` - 蓝色 `#1565c0`
- `contradicts` - 红色 `#c62828`
- `evidence` - 棕色 `#5d4037`
- `conflict` - 深红 `#b71c1c`
- `default` - 灰色 `#90a4ae`

### 节点大小计算

```python
size = base_size + (confidence * 10)
if is_critical_path:
    size *= 1.3
```

---

## 数据模型

### 推理轨迹可视化流程

```
ReasoningTrace
    ↓
遍历节点（thoughts、observations、conclusions）
    ↓
生成 VisNode（计算颜色、大小、元数据）
    ↓
遍历边（因果关系、证据链接）
    ↓
生成 VisEdge（计算权重、颜色）
    ↓
标记关键路径（高亮显示）
    ↓
VisGraph（JSON 序列化）
    ↓
前端 D3.js 渲染
```

### 验证报告可视化流程

```
VerificationReport
    ↓
遍历事实与证据
    ↓
生成 VisNode（事实、证据、冲突）
    ↓
生成 VisEdge（支持、矛盾关系）
    ↓
VisGraph（JSON 序列化）
    ↓
前端 D3.js 渲染
```

---

## 测试与质量

### 测试文件

- `tests/unit/test_visualization.py` - 单元测试（数据生成、颜色计算、序列化）

### 测试覆盖

- 推理轨迹转换
- 验证报告转换
- 节点颜色与大小计算
- 关键路径标记
- JSON 序列化
- 空数据处理

---

## 常见问题 (FAQ)

**Q: 如何自定义节点颜色？**
A: 修改 `_type_colors` 字典，或在初始化时传入自定义颜色映射。

**Q: 如何调整节点大小？**
A: 修改 `base_node_size` 参数，或重写 `_node_size()` 方法。

**Q: 支持哪些布局算法？**
A: 当前默认 `force`（力导向布局），可扩展支持 `hierarchical`（层次布局）、`circular`（环形布局）。

**Q: 如何高亮关键路径？**
A: 推理轨迹中标记为 `critical_path` 的节点会自动放大 1.3 倍并添加元数据标记。

**Q: 前端如何使用生成的数据？**
A: 参考 `frontend/src/pages/Visualization/index.tsx`，使用 D3.js 的 `forceSimulation` 渲染。

---

## 相关文件清单

```
src/epip/visualization/
├── data_generator.py      # 可视化数据生成器（100+ 行）
└── __init__.py            # 模块导出
```

---

## 下一步建议

- 补充层次布局与环形布局支持
- 实现节点过滤与聚合（大图优化）
- 添加交互式元数据展示（tooltip）
- 支持导出 SVG/PNG 图片
- 集成时间轴动画（推理过程回放）
