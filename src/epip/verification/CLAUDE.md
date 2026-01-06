[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **verification**

# verification - 事实验证与溯源

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

对 LLM 生成的事实进行知识图谱验证，提供证据溯源、推理轨迹记录与验证报告生成能力。

核心能力：
- 事实提取与结构化
- 知识图谱证据检索
- 事实验证（支持、部分支持、未验证、矛盾）
- 证据溯源与冲突检测
- 推理轨迹记录与可视化
- 验证报告生成

---

## 入口与启动

### 主要文件

- `fact_verifier.py` - 事实验证器
- `fact_extractor.py` - 事实提取器
- `provenance.py` - 溯源管理
- `trace.py` - 推理轨迹记录
- `path_analyzer.py` - 路径分析器
- `report.py` - 验证报告生成器

### 初始化示例

```python
from epip.verification.fact_verifier import FactVerifier
from epip.verification.fact_extractor import FactExtractor, ExtractedFact
from epip.core.llm_backend import create_llm_backend
from epip.db.neo4j_client import Neo4jClient

# 初始化组件
kg_client = Neo4jClient(...)
llm_backend = create_llm_backend(config)

# 事实提取器
extractor = FactExtractor(llm_backend=llm_backend)

# 事实验证器
verifier = FactVerifier(
    kg_client=kg_client,
    llm_backend=llm_backend,
    evidence_limit=5
)

# 完整流程
text = "2023年政府推出了女性创业扶持政策"
facts = await extractor.extract(text)
results = await verifier.verify_batch(facts)

for result in results:
    print(f"事实: {result.fact.statement}")
    print(f"状态: {result.status.value}")
    print(f"置信度: {result.confidence}")
    print(f"证据数: {len(result.evidences)}")
```

---

## 对外接口

### FactVerifier

**核心方法**：
- `verify(fact: ExtractedFact) -> VerificationResult` - 验证单个事实
- `verify_batch(facts: list[ExtractedFact]) -> list[VerificationResult]` - 批量验证
- `find_kg_evidence(fact: ExtractedFact) -> list[Evidence]` - 检索知识图谱证据
- `calculate_confidence(evidences: list[Evidence]) -> float` - 计算置信度

### VerificationStatus

```python
class VerificationStatus(str, Enum):
    VERIFIED = "verified"                    # 完全验证
    PARTIALLY_VERIFIED = "partial"           # 部分验证
    UNVERIFIED = "unverified"                # 未验证
    CONTRADICTED = "contradicted"            # 矛盾
```

### VerificationResult

```python
@dataclass
class VerificationResult:
    fact: ExtractedFact                      # 待验证事实
    status: VerificationStatus               # 验证状态
    confidence: float                        # 置信度（0-1）
    evidences: list[Evidence]                # 支持证据
    conflicts: list[Evidence]                # 冲突证据
    explanation: str                         # 验证说明
```

### Evidence

```python
@dataclass
class Evidence:
    source_type: str                         # 来源类型（node、relationship、document）
    source_id: str                           # 来源 ID
    content: str                             # 证据内容
    confidence: float                        # 证据置信度
```

### ExtractedFact

```python
@dataclass
class ExtractedFact:
    statement: str                           # 事实陈述
    subject: str                             # 主体
    predicate: str                           # 谓词
    object: str                              # 客体
    metadata: dict[str, Any]                 # 元数据（时间、来源等）
```

---

## 关键依赖与配置

### 依赖项

- `epip.core.llm_backend` - LLM 后端（用于事实提取与解释生成）
- `epip.db.neo4j_client` - Neo4j 客户端（用于证据检索）
- `structlog` - 结构化日志

### 配置参数

- `evidence_limit` - 单个事实最大证据数（默认 5）

### 验证逻辑

```python
if 支持证据存在 and 无冲突 and 置信度 >= 0.85:
    状态 = VERIFIED
elif 支持证据存在 and (置信度 >= 0.5 or 有冲突):
    状态 = PARTIALLY_VERIFIED
elif 仅有冲突证据:
    状态 = CONTRADICTED
else:
    状态 = UNVERIFIED
```

---

## 数据模型

### 验证流程

```
输入文本
    ↓
事实提取（FactExtractor）
    ↓
结构化事实（ExtractedFact）
    ↓
知识图谱检索（find_kg_evidence）
    ↓
证据分类（支持 vs 冲突）
    ↓
置信度计算
    ↓
验证结果（VerificationResult）
    ↓
报告生成（可选）
```

### 推理轨迹结构

见 `trace.py`，包含：
- 推理节点（思考、行动、观察）
- 推理边（因果关系、证据链接）
- 关键路径标记
- 时间戳与元数据

---

## 测试与质量

### 测试文件

- `tests/unit/test_fact_verification.py` - 单元测试（验证器、提取器、溯源）

### 测试覆盖

- 事实提取准确性
- 验证状态判断
- 证据检索与排序
- 置信度计算
- 批量验证并发性
- 异常处理与降级

---

## 常见问题 (FAQ)

**Q: 如何提高验证准确率？**
A: 1) 优化事实提取提示词；2) 扩展知识图谱覆盖；3) 调整置信度阈值；4) 引入外部知识源。

**Q: 验证失败怎么办？**
A: 检查 `VerificationResult.explanation` 字段，查看失败原因（无证据、冲突、低置信度）。

**Q: 如何处理矛盾证据？**
A: 系统会记录所有冲突证据到 `conflicts` 字段，由上层决策（人工审核、多数投票等）。

**Q: 置信度如何计算？**
A: 基于证据数量、证据质量、来源可信度等因素加权计算。具体算法见 `calculate_confidence()`。

**Q: 如何查看推理轨迹？**
A: 调用 `trace.py` 生成 `ReasoningTrace` 对象，或通过 API `/api/visualization/trace/{trace_id}` 查看。

---

## 相关文件清单

```
src/epip/verification/
├── fact_verifier.py       # 事实验证器（100+ 行）
├── fact_extractor.py      # 事实提取器
├── provenance.py          # 溯源管理
├── trace.py               # 推理轨迹记录
├── path_analyzer.py       # 路径分析器
├── report.py              # 验证报告生成器
└── __init__.py            # 模块导出
```

---

## 下一步建议

- 补充外部知识源集成（Wikipedia、Wikidata）
- 实现证据权重学习（基于历史验证结果）
- 扩展验证策略（多数投票、专家系统）
- 添加验证报告模板（PDF、HTML）
- 优化批量验证性能（并发控制、缓存）
