# EPIP 企业政策洞察平台 - 测试策略文档

**版本**: 1.0
**日期**: 2025-12-31
**状态**: 草稿

---

## 1. 引言

本文档定义 EPIP 项目的测试策略，包括早期风险分析、测试方法、质量指标验证方案和测试基础设施规划。

**与架构的关系**：基于 `docs/architecture.md` 定义的组件结构设计测试覆盖，验证 `docs/prd.md` 中的功能需求和非功能需求。

### 1.1 变更日志

| 日期 | 版本 | 描述 | 作者 |
|------|------|------|------|
| 2025-12-31 | 1.0 | 初始测试策略文档 | QA Agent |

---

## 2. 早期风险分析

### 2.1 高风险领域

| 风险 ID | 风险描述 | 影响 | 可能性 | 缓解策略 |
|---------|----------|------|--------|----------|
| R1 | Light-RAG 实体识别准确率不达标 (<90%) | 高 | 中 | 分阶段评估，建立标注基准，参数调优迭代 |
| R2 | 异构 CSV 数据质量问题导致 KG 构建失败 | 高 | 高 | 预处理管道验证，数据质量门控 |
| R3 | ReAct 多步推理性能不满足 2-5x 提升目标 | 高 | 中 | 性能基准测试，缓存优化，查询计划分析 |
| R4 | 幻觉率超过 5% 阈值 | 高 | 中 | 多维度验证，置信度过滤，溯源验证 |
| R5 | Neo4j GDS 算法在大图上性能退化 | 中 | 中 | 索引优化，分区策略，性能监控 |
| R6 | Light-RAG 与 Neo4j 集成兼容性问题 | 中 | 低 | 早期集成测试，版本锁定 |
| R7 | PDF 数据字典解析准确性不足 | 中 | 中 | PDF 解析验证，结构化提取测试 |

### 2.2 风险矩阵

```
影响
  ↑
高 │  R2    R1,R3,R4
   │
中 │  R7    R5,R6
   │
低 │
   └──────────────────→ 可能性
        低    中    高
```

### 2.3 关键依赖风险

1. **Light-RAG 框架成熟度**: 作为核心框架，其稳定性直接影响项目进度
2. **LLM 后端可用性**: Ollama 本地部署或 OpenAI API 的稳定性
3. **数据集完整性**: 24 个 CSV + 4 个 PDF 的数据质量和一致性

---

## 3. 测试策略

### 3.1 测试金字塔

```
                    ┌─────────────┐
                    │   E2E 测试   │  10%
                    │  (关键流程)  │
                   ┌┴─────────────┴┐
                   │   集成测试     │  20%
                   │ (模块交互)    │
                  ┌┴───────────────┴┐
                  │     单元测试      │  70%
                  │   (核心逻辑)     │
                  └──────────────────┘
```

### 3.2 测试层级详情

#### 3.2.1 单元测试 (70%)

**目标覆盖率**: 80%

| 模块 | 测试重点 | 优先级 |
|------|----------|--------|
| DataProcessor | CSV 编码检测、缺失值处理、数据验证 | P0 |
| KGBuilder | Light-RAG 配置、实体映射、关系提取 | P0 |
| QueryEngine | 查询解析、Cypher 生成、ReAct 循环 | P0 |
| HallucinationDetector | 语义匹配、数值验证、置信度计算 | P0 |
| API routes | 请求验证、响应格式、错误处理 | P1 |
| Utilities | 日志、配置、辅助函数 | P2 |

**测试框架**: pytest + pytest-cov

```python
# 示例测试结构
tests/
├── unit/
│   ├── test_data_processor.py
│   │   ├── test_detect_encoding()
│   │   ├── test_handle_missing_values()
│   │   └── test_validate_csv_format()
│   ├── test_kg_builder.py
│   │   ├── test_lightrag_config()
│   │   ├── test_entity_extraction()
│   │   └── test_relationship_mapping()
│   ├── test_query_engine.py
│   │   ├── test_parse_natural_language()
│   │   ├── test_generate_cypher()
│   │   └── test_react_loop()
│   └── test_hallucination.py
│       ├── test_semantic_matching()
│       ├── test_numeric_validation()
│       └── test_confidence_scoring()
```

#### 3.2.2 集成测试 (20%)

**测试重点**: 模块间交互、数据流完整性

| 测试场景 | 涉及组件 | 验证点 |
|----------|----------|--------|
| 数据导入流程 | DataProcessor → KGBuilder → Neo4j | 数据完整性、实体正确性 |
| 查询处理流程 | API → QueryEngine → KGBuilder → Neo4j | 端到端响应、结果准确性 |
| 幻觉检测流程 | QueryEngine → HallucinationDetector | 验证触发、置信度计算 |
| 缓存机制 | QueryEngine → Redis | 缓存命中、TTL 行为 |

**测试基础设施**: Testcontainers (Neo4j, Redis)

```python
# 示例集成测试
tests/
├── integration/
│   ├── test_data_pipeline.py
│   │   └── test_csv_to_neo4j_flow()
│   ├── test_query_pipeline.py
│   │   └── test_nl_query_to_response()
│   └── test_caching.py
│       └── test_redis_cache_behavior()
```

#### 3.2.3 端到端测试 (10%)

**测试重点**: 关键用户场景、业务流程

| 场景 | 描述 | 验收标准 |
|------|------|----------|
| 完整数据导入 | 导入所有 CSV/PDF，构建 KG | 实体数 >1000，关系覆盖 >80% |
| 复杂查询 | 医疗影响链查询 | 响应时间 <5s，结果有溯源 |
| 幻觉检测 | 验证生成内容准确性 | 置信度 >0.7 的结果通过验证 |

---

## 4. 质量指标验证方案

### 4.1 实体准确率验证 (目标 >90%)

#### 4.1.1 评估方法

1. **标注基准构建**:
   - 从每个 CSV 随机抽样 50 条记录
   - 人工标注期望的实体（类型、名称、属性）
   - 总计约 1200 条标注记录（24 CSV × 50）

2. **自动化评估脚本**:
   ```python
   def evaluate_entity_accuracy(extracted: List[Entity],
                                 ground_truth: List[Entity]) -> float:
       """
       计算实体准确率
       - 精确匹配: 名称和类型完全一致
       - 模糊匹配: 名称相似度 >0.9 且类型一致
       """
       exact_matches = count_exact_matches(extracted, ground_truth)
       fuzzy_matches = count_fuzzy_matches(extracted, ground_truth)
       return (exact_matches + 0.5 * fuzzy_matches) / len(ground_truth)
   ```

3. **评估维度**:
   | 维度 | 指标 | 阈值 |
   |------|------|------|
   | 实体识别 | Precision | >90% |
   | 实体识别 | Recall | >85% |
   | 实体分类 | Accuracy | >90% |
   | 实体消歧 | Dedup Rate | >95% |

#### 4.1.2 测试数据集

```
tests/fixtures/
├── entity_ground_truth/
│   ├── health_stats_entities.json
│   ├── hospital_admission_entities.json
│   └── ...
```

### 4.2 关系覆盖率验证 (目标 >80%)

#### 4.2.1 评估方法

1. **预期关系定义**:
   - 基于 PDF 数据字典定义实体间的预期关系
   - 定义关系类型：AFFECTS, CONTAINS, RELATED_TO, TEMPORAL, etc.

2. **覆盖率计算**:
   ```python
   def evaluate_relation_coverage(extracted: List[Relation],
                                   expected: List[RelationType]) -> float:
       """
       计算关系覆盖率
       - 检查每种预期关系类型是否被提取
       - 计算实际提取的关系数量占预期的比例
       """
       covered_types = set(r.type for r in extracted)
       coverage = len(covered_types & expected) / len(expected)
       return coverage
   ```

3. **评估维度**:
   | 维度 | 指标 | 阈值 |
   |------|------|------|
   | 关系类型覆盖 | Type Coverage | >80% |
   | 关系实例覆盖 | Instance Coverage | >75% |
   | 跨文件关联 | Cross-file Links | >50% |

### 4.3 查询性能验证 (目标 2-5x 提升)

#### 4.3.1 基准测试设计

1. **查询分类**:
   | 类型 | 描述 | 示例数量 |
   |------|------|----------|
   | 简单查询 | 单实体检索 | 10 |
   | 中等查询 | 2-3 跳路径查询 | 10 |
   | 复杂查询 | 多步推理、影响链 | 10 |

2. **基准对比**:
   - **Baseline**: 直接 Cypher 查询（无优化）
   - **Optimized**: Light-RAG + 缓存 + GDS 算法

3. **性能指标**:
   ```python
   @dataclass
   class PerformanceMetrics:
       query_type: str
       baseline_latency_p50: float  # ms
       baseline_latency_p99: float  # ms
       optimized_latency_p50: float
       optimized_latency_p99: float
       speedup_ratio: float
       cache_hit_rate: float
   ```

#### 4.3.2 性能测试脚本

```python
# scripts/benchmark_queries.py
def run_benchmark():
    """
    运行查询性能基准测试
    输出: benchmark_report.md
    """
    queries = load_benchmark_queries()
    results = []

    for query in queries:
        baseline = measure_baseline(query)
        optimized = measure_optimized(query)
        results.append(PerformanceMetrics(
            speedup_ratio=baseline.p50 / optimized.p50
        ))

    generate_report(results)
```

### 4.4 幻觉率验证 (目标 <5%)

#### 4.4.1 测试集设计

1. **测试样本构成**:
   | 类型 | 数量 | 描述 |
   |------|------|------|
   | 事实性问题 | 50 | 有明确 KG 答案的问题 |
   | 推理性问题 | 30 | 需要多步推理的问题 |
   | 边界问题 | 20 | 接近 KG 边界的问题 |

2. **幻觉分类**:
   | 类型 | 定义 | 检测方法 |
   |------|------|----------|
   | 实体幻觉 | 生成 KG 中不存在的实体 | 实体存在性验证 |
   | 关系幻觉 | 生成不存在的关系 | 关系路径验证 |
   | 数值幻觉 | 数字与 KG 不一致 | 数值精确匹配 |
   | 推理幻觉 | 推理逻辑错误 | 路径一致性检查 |

#### 4.4.2 评估脚本

```python
def evaluate_hallucination_rate(responses: List[Response],
                                 kg_context: GraphContext) -> float:
    """
    计算幻觉率
    """
    hallucinations = 0
    for response in responses:
        if not verify_entities(response, kg_context):
            hallucinations += 1
        elif not verify_relations(response, kg_context):
            hallucinations += 1
        elif not verify_numeric(response, kg_context):
            hallucinations += 1

    return hallucinations / len(responses)
```

---

## 5. 测试基础设施

### 5.1 测试环境

| 环境 | 用途 | 配置 |
|------|------|------|
| Local | 开发测试 | Docker Compose (单实例) |
| CI | 自动化测试 | GitHub Actions + Testcontainers |
| Staging | 预发布验证 | Docker Compose (生产配置) |

### 5.2 CI/CD 集成

```yaml
# .github/workflows/test.yml
name: Test Pipeline

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run unit tests
        run: pytest tests/unit -v --cov=src/epip --cov-report=xml
      - name: Check coverage
        run: |
          coverage=$(python -c "import xml.etree.ElementTree as ET; print(float(ET.parse('coverage.xml').getroot().get('line-rate'))*100)")
          if (( $(echo "$coverage < 80" | bc -l) )); then
            echo "Coverage $coverage% is below 80%"
            exit 1
          fi

  integration-tests:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5-community
        ports:
          - 7687:7687
        env:
          NEO4J_AUTH: neo4j/testpassword
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - name: Run integration tests
        run: pytest tests/integration -v

  quality-gates:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - name: Run quality benchmarks
        run: |
          python scripts/evaluate_entity_accuracy.py
          python scripts/evaluate_relation_coverage.py
          python scripts/benchmark_queries.py
      - name: Check quality thresholds
        run: python scripts/check_quality_gates.py
```

### 5.3 质量门控

```python
# scripts/check_quality_gates.py
QUALITY_GATES = {
    "entity_accuracy": {"threshold": 0.90, "blocking": True},
    "relation_coverage": {"threshold": 0.80, "blocking": True},
    "query_speedup": {"threshold": 2.0, "blocking": False},
    "hallucination_rate": {"threshold": 0.05, "blocking": True},
    "test_coverage": {"threshold": 0.80, "blocking": True},
}

def check_gates(metrics: dict) -> bool:
    """检查所有质量门控，阻断性失败返回 False"""
    for gate, config in QUALITY_GATES.items():
        if gate in metrics:
            passed = metrics[gate] >= config["threshold"]
            if not passed and config["blocking"]:
                print(f"FAILED: {gate} = {metrics[gate]} < {config['threshold']}")
                return False
    return True
```

---

## 6. 测试数据管理

### 6.1 测试数据集结构

```
tests/
├── fixtures/
│   ├── csv_samples/           # CSV 测试样本
│   │   ├── health_stats_sample.csv
│   │   └── hospital_admission_sample.csv
│   ├── pdf_samples/           # PDF 测试样本
│   │   └── data_dictionary_sample.pdf
│   ├── entity_ground_truth/   # 实体标注基准
│   │   └── entities.json
│   ├── relation_ground_truth/ # 关系标注基准
│   │   └── relations.json
│   ├── query_benchmark/       # 查询基准测试集
│   │   ├── simple_queries.json
│   │   ├── medium_queries.json
│   │   └── complex_queries.json
│   └── hallucination_test/    # 幻觉检测测试集
│       └── test_cases.json
```

### 6.2 Mock 策略

| 组件 | Mock 方式 | 用途 |
|------|----------|------|
| LLM | 固定响应 | 单元测试稳定性 |
| Neo4j | Testcontainers | 集成测试真实性 |
| Redis | Testcontainers | 缓存行为验证 |
| Light-RAG | 部分 Mock | 隔离测试各阶段 |

---

## 7. 测试执行计划

### 7.1 阶段性测试

| 阶段 | 测试类型 | 关注点 | 完成标准 |
|------|----------|--------|----------|
| Epic 1 完成 | 冒烟测试 | Light-RAG 集成 | 基本功能可用 |
| Epic 2 完成 | 质量测试 | KG 准确性 | 实体 >90%, 关系 >80% |
| Epic 3 完成 | 性能测试 | 查询速度 | 提升 >2x |
| Epic 4 完成 | 验证测试 | 幻觉率 | <5% |

### 7.2 回归测试

- **触发条件**: 每次代码合并到 main 分支
- **范围**: 全量单元测试 + 关键集成测试
- **超时**: 30 分钟

---

## 8. 检查清单结果

*待测试策略审核通过后执行 QA 检查清单*

---

## 9. 下一步

### 9.1 PO 验证提示词

```
请基于 docs/prd.md、docs/architecture.md 和 docs/test-strategy.md 验证 EPIP 项目文档的一致性和完整性。

检查项：
1. PRD 需求是否完全被架构覆盖
2. 质量指标是否有对应的测试方案
3. 技术栈选择是否一致
4. 风险是否被充分识别和缓解

输出：验证报告，标注任何不一致或遗漏。
```

### 9.2 分片提示词

```
请将 EPIP 项目的 Epic 1 分片为可执行的 Story 文件。

参考：
- PRD: docs/prd.md (Epic 1, Story 1.1-1.4)
- 架构: docs/architecture.md
- 测试策略: docs/test-strategy.md

输出格式：每个 Story 一个 Markdown 文件，包含详细的验收标准和技术任务。
```
