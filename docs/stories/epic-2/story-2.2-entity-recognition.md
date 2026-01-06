# Story 2.2: Light-RAG 实体识别与消歧

**Epic**: Epic 2 - 知识图谱构建与优化
**优先级**: P0
**估算**: 中型

---

## 用户故事

**作为** 知识工程师，
**我想要** 通过 Light-RAG 完成实体识别和消歧，
**以便** 获得高质量的实体节点。

---

## 验收标准

### AC1: 实体识别参数配置
- [ ] 配置 Light-RAG 的实体提取提示词
- [ ] 设置置信度阈值 >0.5
- [ ] 支持自定义实体类型列表
- [ ] 配置参数可通过环境变量覆盖

### AC2: 实体消歧功能
- [ ] 验证 Light-RAG 的同义实体合并
- [ ] 实现基于嵌入相似度的实体匹配
- [ ] 处理中英文实体名称变体
- [ ] 记录消歧操作日志

### AC3: 实体类型管理
- [ ] 定义领域实体类型（政策、机构、人物、地点、日期、指标等）
- [ ] 支持实体类型层级（如：机构 → 政府部门/医院/学校）
- [ ] 实体类型验证和修正

### AC4: 实体识别报告
- [ ] 统计各类型实体数量
- [ ] 计算实体消歧率
- [ ] 识别低置信度实体
- [ ] 输出 Markdown 格式报告

### AC5: 准确率评估基准
- [ ] 创建标注样本（50-100 个实体）
- [ ] 实现准确率计算脚本
- [ ] 目标：实体准确率 >90%
- [ ] 集成到测试流程

---

## 技术任务

### Task 2.2.1: 实体提取配置
```python
# src/epip/core/entity_extractor.py

from dataclasses import dataclass, field
from typing import Literal

@dataclass
class EntityExtractionConfig:
    """实体提取配置"""
    confidence_threshold: float = 0.5
    entity_types: list[str] = field(default_factory=lambda: [
        "POLICY",      # 政策
        "ORGANIZATION", # 机构
        "PERSON",      # 人物
        "LOCATION",    # 地点
        "DATE",        # 日期
        "METRIC",      # 指标
        "DISEASE",     # 疾病
        "BUDGET",      # 预算
    ])
    max_entities_per_chunk: int = 50
    enable_disambiguation: bool = True
    similarity_threshold: float = 0.85  # 消歧相似度阈值
```

### Task 2.2.2: 实体消歧器
```python
# src/epip/core/entity_extractor.py (续)

class EntityDisambiguator:
    """基于嵌入的实体消歧"""

    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold
        self._embedding_model = None

    async def find_similar_entities(
        self,
        entity_name: str,
        candidates: list[str]
    ) -> list[tuple[str, float]]:
        """查找相似实体"""
        # 使用 sentence-transformers 计算相似度
        pass

    async def merge_entities(
        self,
        entity_pairs: list[tuple[str, str]]
    ) -> int:
        """合并相似实体"""
        pass
```

### Task 2.2.3: 实体报告生成
```python
# src/epip/core/entity_extractor.py (续)

@dataclass
class EntityReport:
    """实体识别报告"""
    total_entities: int
    entity_type_counts: dict[str, int]
    low_confidence_count: int
    disambiguation_count: int
    sample_entities: list[dict]  # 样本实体列表

class EntityReportGenerator:
    """生成实体识别报告"""

    async def generate_report(self, kg_builder: KGBuilder) -> EntityReport:
        """从知识图谱生成实体报告"""
        pass

    def export_markdown(self, report: EntityReport, output_path: Path) -> Path:
        """导出 Markdown 报告"""
        pass
```

### Task 2.2.4: 准确率评估
```python
# src/epip/core/entity_extractor.py (续)

@dataclass
class EvaluationResult:
    """评估结果"""
    precision: float
    recall: float
    f1_score: float
    confusion_matrix: dict[str, dict[str, int]]

class EntityEvaluator:
    """实体准确率评估"""

    def __init__(self, ground_truth_path: Path):
        self.ground_truth = self._load_ground_truth(ground_truth_path)

    def evaluate(self, extracted_entities: list[dict]) -> EvaluationResult:
        """评估实体识别准确率"""
        pass
```

### Task 2.2.5: 创建评估脚本
```python
# scripts/evaluate_entities.py

async def main():
    """实体评估主流程"""
    # 1. 加载标注数据
    # 2. 从 KG 提取实体
    # 3. 计算准确率
    # 4. 生成报告
```

---

## 测试用例

### 单元测试
- [ ] 测试 `EntityExtractionConfig` 默认值
- [ ] 测试 `find_similar_entities()` 相似度计算
- [ ] 测试 `EntityReport` 统计计算
- [ ] 测试 `evaluate()` 准确率计算

### 集成测试
- [ ] 测试完整实体提取流程
- [ ] 测试消歧后实体数量变化
- [ ] 测试报告生成

### 验收测试
- [ ] 实体准确率 >90%
- [ ] 消歧率符合预期
- [ ] 报告格式正确

---

## 依赖关系

- **前置**: Story 2.1（需要导入数据后才能评估实体）
- **后置**: Story 2.3（关系提取依赖实体质量）

---

## 相关文档

- 架构: `docs/architecture.md`
- Light-RAG: `src/epip/core/kg_builder.py`
- 数据字典: `dataset/*.pdf`（包含领域实体定义）
