# Story 4.1: 事实一致性验证

**Epic**: Epic 4 - 幻觉检测与可追溯性
**优先级**: P0
**估算**: 大型

---

## 用户故事

**作为** 终端用户，
**我想要** 系统验证答案中每个事实的可靠性，
**以便** 确保获得的信息是准确且可信的。

---

## 验收标准

### AC1: 事实提取
- [ ] 从答案中提取可验证的事实声明
- [ ] 识别事实类型（数字、日期、关系、属性）
- [ ] 标记事实来源（KG节点/边）
- [ ] 处理复合事实分解

### AC2: KG 事实验证
- [ ] 在知识图谱中查找支持证据
- [ ] 计算事实置信度分数
- [ ] 检测与 KG 的矛盾
- [ ] 处理部分匹配情况

### AC3: 多源交叉验证
- [ ] 收集多个支持证据
- [ ] 计算证据一致性分数
- [ ] 检测证据冲突
- [ ] 生成综合置信度

### AC4: 验证报告
- [ ] 生成每个事实的验证状态
- [ ] 标注置信度等级（高/中/低）
- [ ] 提供证据引用
- [ ] 输出结构化验证结果

### AC5: 弱证据过滤
- [ ] 过滤置信度 < 0.7 的事实
- [ ] 标记可疑声明
- [ ] 提供替代建议
- [ ] 记录过滤原因

---

## 技术任务

### Task 4.1.1: 事实提取器
```python
# src/epip/verification/fact_extractor.py

from dataclasses import dataclass
from enum import Enum

class FactType(Enum):
    NUMERIC = "numeric"       # 数值事实
    TEMPORAL = "temporal"     # 时间事实
    RELATION = "relation"     # 关系事实
    ATTRIBUTE = "attribute"   # 属性事实
    COMPOSITE = "composite"   # 复合事实

@dataclass
class ExtractedFact:
    """提取的事实"""
    fact_id: str
    content: str
    fact_type: FactType
    subject: str
    predicate: str | None
    object: str | None
    source_span: tuple[int, int]  # 在原文中的位置
    sub_facts: list["ExtractedFact"] | None = None  # 复合事实的子事实

class FactExtractor:
    """事实提取器"""

    def extract(self, text: str) -> list[ExtractedFact]:
        """从文本中提取事实"""
        pass

    def decompose_composite(self, fact: ExtractedFact) -> list[ExtractedFact]:
        """分解复合事实"""
        pass

    def classify_fact_type(self, fact: ExtractedFact) -> FactType:
        """分类事实类型"""
        pass
```

### Task 4.1.2: 事实验证器
```python
# src/epip/verification/fact_verifier.py

from dataclasses import dataclass
from enum import Enum

class VerificationStatus(Enum):
    VERIFIED = "verified"           # 已验证
    PARTIALLY_VERIFIED = "partial"  # 部分验证
    UNVERIFIED = "unverified"       # 未验证
    CONTRADICTED = "contradicted"   # 矛盾

@dataclass
class Evidence:
    """支持证据"""
    source_type: str  # "kg_node", "kg_edge", "document"
    source_id: str
    content: str
    confidence: float

@dataclass
class VerificationResult:
    """验证结果"""
    fact: ExtractedFact
    status: VerificationStatus
    confidence: float
    evidences: list[Evidence]
    conflicts: list[Evidence] | None = None
    explanation: str = ""

class FactVerifier:
    """事实验证器"""

    def __init__(self, kg_client, llm_backend):
        pass

    async def verify(self, fact: ExtractedFact) -> VerificationResult:
        """验证单个事实"""
        pass

    async def verify_batch(self, facts: list[ExtractedFact]) -> list[VerificationResult]:
        """批量验证事实"""
        pass

    async def find_kg_evidence(self, fact: ExtractedFact) -> list[Evidence]:
        """在 KG 中查找证据"""
        pass

    def calculate_confidence(self, evidences: list[Evidence]) -> float:
        """计算综合置信度"""
        pass
```

### Task 4.1.3: 验证报告生成器
```python
# src/epip/verification/report.py

from dataclasses import dataclass
from enum import Enum

class ConfidenceLevel(Enum):
    HIGH = "high"      # >= 0.85
    MEDIUM = "medium"  # >= 0.7
    LOW = "low"        # < 0.7

@dataclass
class VerificationReport:
    """验证报告"""
    answer_id: str
    total_facts: int
    verified_count: int
    partial_count: int
    unverified_count: int
    contradicted_count: int
    overall_confidence: float
    results: list[VerificationResult]
    filtered_facts: list[ExtractedFact]  # 被过滤的弱证据事实

class ReportGenerator:
    """报告生成器"""

    def generate(self, results: list[VerificationResult]) -> VerificationReport:
        """生成验证报告"""
        pass

    def filter_weak_facts(
        self,
        results: list[VerificationResult],
        threshold: float = 0.7
    ) -> tuple[list[VerificationResult], list[ExtractedFact]]:
        """过滤弱证据事实"""
        pass

    def to_markdown(self, report: VerificationReport) -> str:
        """输出 Markdown 格式报告"""
        pass

    def to_json(self, report: VerificationReport) -> dict:
        """输出 JSON 格式报告"""
        pass
```

---

## 测试用例

### 单元测试
- [ ] 测试 `extract()` 事实提取
- [ ] 测试 `decompose_composite()` 复合事实分解
- [ ] 测试 `verify()` 单事实验证
- [ ] 测试 `find_kg_evidence()` 证据查找
- [ ] 测试 `filter_weak_facts()` 弱证据过滤

### 集成测试
- [ ] 测试完整验证流程
- [ ] 测试多源交叉验证
- [ ] 测试矛盾检测

### 验收测试
- [ ] 事实提取准确率 ≥ 90%
- [ ] 验证置信度合理分布
- [ ] 弱证据正确过滤

---

## 依赖关系

- **前置**: Story 3.3（需要 ReAct 推理结果）
- **后置**: Story 4.2（推理路径追踪）
