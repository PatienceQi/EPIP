# Story 2.5: KG 质量评估与报告

**Epic**: Epic 2 - 知识图谱构建与优化
**优先级**: P1
**估算**: 中型

---

## 用户故事

**作为** 项目经理，
**我想要** 自动化的 KG 质量评估报告，
**以便** 跟踪和验证质量指标。

---

## 验收标准

### AC1: 实体准确率评估
- [ ] 加载标注样本数据
- [ ] 与 KG 中实体进行对比
- [ ] 计算 Precision、Recall、F1 Score
- [ ] 目标：实体准确率 >90%

### AC2: 关系覆盖率评估
- [ ] 定义预期关系集合
- [ ] 计算已覆盖关系比例
- [ ] 识别缺失的关键关系
- [ ] 目标：关系覆盖率 >80%

### AC3: 图连通性指标
- [ ] 计算连通分量数
- [ ] 计算平均路径长度
- [ ] 计算图密度
- [ ] 识别孤立节点比例

### AC4: 综合质量报告
- [ ] 汇总所有质量指标
- [ ] 生成 Markdown 格式报告
- [ ] 包含趋势对比（与上次评估）
- [ ] 可视化质量分数（ASCII 图表）

### AC5: CI 集成与告警
- [ ] 创建质量评估脚本
- [ ] 定义质量阈值配置
- [ ] 质量低于阈值时返回非零退出码
- [ ] 输出机器可读的 JSON 结果

---

## 技术任务

### Task 2.5.1: 质量评估器
```python
# src/epip/core/kg_quality.py

from dataclasses import dataclass
from pathlib import Path

@dataclass
class QualityThresholds:
    """质量阈值配置"""
    entity_precision: float = 0.90
    entity_recall: float = 0.85
    relation_coverage: float = 0.80
    max_isolated_ratio: float = 0.05
    max_components: int = 3

@dataclass
class EntityQualityMetrics:
    """实体质量指标"""
    precision: float
    recall: float
    f1_score: float
    total_expected: int
    total_found: int
    missing_entities: list[str]

@dataclass
class RelationQualityMetrics:
    """关系质量指标"""
    coverage: float
    total_expected: int
    total_found: int
    missing_relations: list[tuple[str, str, str]]

@dataclass
class GraphQualityMetrics:
    """图结构质量指标"""
    node_count: int
    edge_count: int
    component_count: int
    isolated_ratio: float
    density: float
    avg_degree: float

@dataclass
class KGQualityReport:
    """综合质量报告"""
    entity_metrics: EntityQualityMetrics
    relation_metrics: RelationQualityMetrics
    graph_metrics: GraphQualityMetrics
    overall_score: float  # 0-100
    passed: bool
    issues: list[str]

class KGQualityEvaluator:
    """知识图谱质量评估器"""

    def __init__(
        self,
        thresholds: QualityThresholds | None = None,
        ground_truth_path: Path | None = None
    ):
        self.thresholds = thresholds or QualityThresholds()
        self.ground_truth_path = ground_truth_path

    async def evaluate_entities(self, kg_builder) -> EntityQualityMetrics:
        """评估实体质量"""
        pass

    async def evaluate_relations(self, kg_builder) -> RelationQualityMetrics:
        """评估关系质量"""
        pass

    async def evaluate_graph(self, kg_builder) -> GraphQualityMetrics:
        """评估图结构质量"""
        pass

    async def generate_report(self, kg_builder) -> KGQualityReport:
        """生成综合质量报告"""
        pass

    def export_markdown(self, report: KGQualityReport, output_path: Path) -> Path:
        """导出 Markdown 报告"""
        pass

    def export_json(self, report: KGQualityReport, output_path: Path) -> Path:
        """导出 JSON 报告（CI 使用）"""
        pass
```

### Task 2.5.2: 质量报告生成器
```python
# src/epip/core/kg_quality.py (续)

class QualityReportGenerator:
    """生成质量报告"""

    def generate_summary(self, report: KGQualityReport) -> str:
        """生成摘要"""
        pass

    def generate_entity_section(self, metrics: EntityQualityMetrics) -> str:
        """生成实体评估章节"""
        pass

    def generate_relation_section(self, metrics: RelationQualityMetrics) -> str:
        """生成关系评估章节"""
        pass

    def generate_graph_section(self, metrics: GraphQualityMetrics) -> str:
        """生成图结构章节"""
        pass

    def generate_ascii_chart(self, scores: dict[str, float]) -> str:
        """生成 ASCII 进度条图表"""
        pass
```

### Task 2.5.3: CI 评估脚本
```python
# scripts/evaluate_kg_quality.py

import sys
import asyncio
import argparse

async def main():
    """KG 质量评估主流程"""
    # 1. 解析参数
    # 2. 加载配置和标注数据
    # 3. 执行评估
    # 4. 生成报告
    # 5. 检查阈值，设置退出码

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
```

### Task 2.5.4: 标注数据格式
```yaml
# data/ground_truth/expected_kg.yaml

entities:
  - name: "香港医院管理局"
    type: "ORGANIZATION"
    required: true
  - name: "医务卫生局"
    type: "ORGANIZATION"
    required: true

relations:
  - source: "香港医院管理局"
    target: "医务卫生局"
    type: "REPORTS_TO"
    required: true
```

---

## 测试用例

### 单元测试
- [ ] 测试 `evaluate_entities()` 准确率计算
- [ ] 测试 `evaluate_relations()` 覆盖率计算
- [ ] 测试 `evaluate_graph()` 连通性计算
- [ ] 测试 `generate_report()` 综合评分
- [ ] 测试阈值检查逻辑

### 集成测试
- [ ] 测试完整评估流程
- [ ] 测试 Markdown 报告生成
- [ ] 测试 JSON 报告生成
- [ ] 测试 CI 退出码

### 验收测试
- [ ] 实体准确率 >90%
- [ ] 关系覆盖率 >80%
- [ ] 报告格式正确完整

---

## 依赖关系

- **前置**: Story 2.4（需要优化后的 KG）
- **后置**: Epic 3（查询处理依赖高质量 KG）

---

## 相关文档

- 架构: `docs/architecture.md`
- 实体评估: `src/epip/core/entity_extractor.py`
- 关系分析: `src/epip/core/relation_extractor.py`
- 标注数据: `data/ground_truth/`
