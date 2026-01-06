# Story 2.3: Light-RAG 关系提取与子图融合

**Epic**: Epic 2 - 知识图谱构建与优化
**优先级**: P0
**估算**: 中型

---

## 用户故事

**作为** 知识工程师，
**我想要** 通过 Light-RAG 完成关系提取和子图融合，
**以便** 构建完整连通的知识图谱。

---

## 验收标准

### AC1: 关系提取参数配置
- [ ] 配置 Light-RAG 的关系提取提示词
- [ ] 设置关系置信度阈值
- [ ] 定义领域关系类型（管辖、资助、发布、影响等）
- [ ] 支持双向/单向关系配置

### AC2: 跨文件实体关联
- [ ] 识别跨文档的相同实体
- [ ] 建立跨文档实体间的关系
- [ ] 记录关系来源追溯信息

### AC3: 子图融合
- [ ] 检测孤立子图
- [ ] 实现子图连接策略
- [ ] 验证融合后图的连通性

### AC4: 图结构完整性验证
- [ ] 检查悬挂节点（无关系的实体）
- [ ] 检查自环关系
- [ ] 验证关系方向一致性
- [ ] 生成图结构健康报告

### AC5: 关系提取报告
- [ ] 统计各类型关系数量
- [ ] 计算图连通性指标
- [ ] 识别高频关系模式
- [ ] 输出 Markdown 格式报告

---

## 技术任务

### Task 2.3.1: 关系提取配置
```python
# src/epip/core/relation_extractor.py

from dataclasses import dataclass, field

@dataclass
class RelationExtractionConfig:
    """关系提取配置"""
    confidence_threshold: float = 0.5
    relation_types: list[str] = field(default_factory=lambda: [
        "GOVERNS",       # 管辖
        "FUNDS",         # 资助
        "PUBLISHES",     # 发布
        "AFFECTS",       # 影响
        "IMPLEMENTS",    # 实施
        "REPORTS_TO",    # 汇报
        "LOCATED_IN",    # 位于
        "RELATED_TO",    # 相关
        "CAUSES",        # 导致
        "TREATS",        # 治疗
    ])
    max_relations_per_chunk: int = 100
    enable_bidirectional: bool = False
    merge_similar_relations: bool = True
```

### Task 2.3.2: 子图分析器
```python
# src/epip/core/relation_extractor.py (续)

@dataclass
class SubgraphInfo:
    """子图信息"""
    node_count: int
    edge_count: int
    is_connected: bool
    components: int  # 连通分量数

class SubgraphAnalyzer:
    """分析和融合子图"""

    async def analyze_connectivity(self, kg_builder: KGBuilder) -> SubgraphInfo:
        """分析图连通性"""
        pass

    async def find_isolated_nodes(self, kg_builder: KGBuilder) -> list[str]:
        """查找孤立节点"""
        pass

    async def suggest_bridges(
        self,
        kg_builder: KGBuilder,
        max_suggestions: int = 10
    ) -> list[tuple[str, str, str]]:
        """建议潜在的桥接关系"""
        pass
```

### Task 2.3.3: 关系报告生成
```python
# src/epip/core/relation_extractor.py (续)

@dataclass
class RelationReport:
    """关系提取报告"""
    total_relations: int
    relation_type_counts: dict[str, int]
    connectivity: SubgraphInfo
    isolated_nodes: list[str]
    top_relation_patterns: list[tuple[str, str, str, int]]  # (src_type, rel, tgt_type, count)

class RelationReportGenerator:
    """生成关系提取报告"""

    async def generate_report(self, kg_builder: KGBuilder) -> RelationReport:
        """从知识图谱生成关系报告"""
        pass

    def export_markdown(self, report: RelationReport, output_path: Path) -> Path:
        """导出 Markdown 报告"""
        pass
```

### Task 2.3.4: 图结构验证器
```python
# src/epip/core/relation_extractor.py (续)

@dataclass
class GraphHealthReport:
    """图结构健康报告"""
    is_healthy: bool
    dangling_nodes: int
    self_loops: int
    inconsistent_directions: int
    issues: list[str]

class GraphValidator:
    """验证图结构完整性"""

    async def validate(self, kg_builder: KGBuilder) -> GraphHealthReport:
        """执行完整性验证"""
        pass

    async def fix_issues(
        self,
        kg_builder: KGBuilder,
        auto_fix: bool = False
    ) -> int:
        """修复发现的问题"""
        pass
```

### Task 2.3.5: 创建分析脚本
```python
# scripts/analyze_relations.py

async def main():
    """关系分析主流程"""
    # 1. 分析连通性
    # 2. 查找孤立节点
    # 3. 验证图结构
    # 4. 生成报告
```

---

## 测试用例

### 单元测试
- [ ] 测试 `RelationExtractionConfig` 默认值
- [ ] 测试 `analyze_connectivity()` 连通性计算
- [ ] 测试 `find_isolated_nodes()` 孤立节点检测
- [ ] 测试 `validate()` 结构验证

### 集成测试
- [ ] 测试完整关系分析流程
- [ ] 测试子图融合后连通性变化
- [ ] 测试报告生成

### 验收测试
- [ ] 关系覆盖率 >80%
- [ ] 图连通分量 ≤3
- [ ] 孤立节点 <5%

---

## 依赖关系

- **前置**: Story 2.2（实体识别完成后才能提取关系）
- **后置**: Story 2.4（手动优化依赖关系质量）

---

## 相关文档

- 架构: `docs/architecture.md`
- 实体: `src/epip/core/entity_extractor.py`
- KG: `src/epip/core/kg_builder.py`
