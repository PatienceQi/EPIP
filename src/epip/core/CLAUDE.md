[根目录](../../CLAUDE.md) > [src](../) > [epip](../) > **core**

# 核心模块 (Core)

> 最后更新：2026-01-06T19:33:46+0800

---

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

核心业务逻辑模块，负责知识图谱构建、查询引擎、幻觉检测、实体/关系提取等核心功能。

核心能力：
- **KG 构建**：基于 Light-RAG 框架构建知识图谱
- **查询引擎**：执行自然语言查询与图检索
- **幻觉检测**：验证 LLM 生成内容的可信度
- **实体提取**：从文本中识别并提取实体
- **关系提取**：分析实体间的关系
- **质量评估**：评估知识图谱质量指标

---

## 入口与启动

主要入口点：
- `kg_builder.py`：知识图谱构建器
- `query_engine.py`：查询引擎
- `hallucination.py`：幻觉检测器

依赖注入：通过 `src/epip/api/dependencies.py` 提供依赖注入。

---

## 对外接口

### KnowledgeGraphBuilder

```python
class KnowledgeGraphBuilder:
    async def build_from_documents(self, documents: list[Document]) -> KGBuildResult
    async def add_entity(self, entity: Entity) -> None
    async def add_relation(self, relation: Relation) -> None
    async def get_entity(self, entity_id: str) -> Entity | None
```

### QueryEngine

```python
class QueryEngine:
    async def query(self, query: str, mode: QueryMode = QueryMode.HYBRID) -> QueryResult
    async def search_entities(self, keywords: list[str]) -> list[Entity]
    async def search_relations(self, source: str, target: str) -> list[Relation]
```

### HallucinationDetector

```python
class HallucinationDetector:
    async def verify(self, answer: str, context: list[str]) -> VerificationResult
    async def extract_claims(self, text: str) -> list[Claim]
    async def check_claim(self, claim: Claim, evidence: list[str]) -> ClaimVerification
```

---

## 关键依赖与配置

### 依赖

- `lightrag-hku`：Light-RAG 框架
- `neo4j`：图数据库客户端
- `sentence-transformers`：嵌入模型
- `openai`：LLM API 客户端

### 配置

通过 `src/epip/config.py` 管理配置：

```python
class LightRAGConfig(BaseSettings):
    working_dir: str = "./data/lightrag"
    graph_storage: Literal["neo4j", "networkx"] = "neo4j"
    llm_backend: Literal["ollama", "openai"] = "ollama"
    llm_model: str = "qwen-plus"
    embedding_model: str = "text-embedding-v4"
    chunk_size: int = 1200
    chunk_overlap: int = 100
```

环境变量：
- `LLM_BINDING`：LLM 后端类型（`ollama` / `openai`）
- `LLM_MODEL`：语言模型名称
- `LLM_API_KEY`：API 密钥
- `EMBEDDING_MODEL`：嵌入模型名称
- `NEO4J_URI`：Neo4j 连接地址
- `NEO4J_PASSWORD`：Neo4j 密码

---

## 数据模型

### Entity

```python
@dataclass
class Entity:
    id: str
    name: str
    type: str
    properties: dict[str, Any]
    confidence: float
```

### Relation

```python
@dataclass
class Relation:
    id: str
    source: str
    target: str
    type: str
    properties: dict[str, Any]
    confidence: float
```

### QueryResult

```python
@dataclass
class QueryResult:
    answer: str
    entities: list[Entity]
    relations: list[Relation]
    confidence: float
    trace_id: str | None
```

---

## 测试与质量

### 单元测试

- `tests/unit/test_kg_builder.py`：KG 构建器测试
- `tests/unit/test_query_engine.py`：查询引擎测试
- `tests/unit/test_hallucination.py`：幻觉检测测试
- `tests/unit/test_entity_extractor.py`：实体提取测试
- `tests/unit/test_relation_extractor.py`：关系提取测试
- `tests/unit/test_kg_quality.py`：质量评估测试

### 集成测试

- `tests/integration/test_e2e_pipeline.py`：端到端流程测试
- `tests/integration/test_component_integration.py`：组件集成测试

### 质量指标

- 实体精度：≥80%
- 实体召回率：≥75%
- 关系覆盖率：≥70%
- 图密度：≥0.01
- 平均度数：≥1.0
- 孤立节点比例：≤10%

---

## 常见问题 (FAQ)

**Q: 如何切换 LLM 后端？**
A: 修改 `.env` 中的 `LLM_BINDING` 和相关 API 配置，重启服务。

**Q: 如何调整实体提取阈值？**
A: 修改 `ENTITY_CONFIDENCE_THRESHOLD` 环境变量（默认 0.6）。

**Q: 如何评估 KG 质量？**
A: 运行 `python scripts/evaluate_kg_quality.py`，查看生成的质量报告。

**Q: 如何优化查询性能？**
A: 启用查询缓存（Redis），调整 `chunk_size` 和 `max_concurrent_llm` 参数。

---

## 相关文件清单

```
src/epip/core/
├── __init__.py
├── kg_builder.py          # KG 构建器
├── query_engine.py        # 查询引擎
├── hallucination.py       # 幻觉检测
├── entity_extractor.py    # 实体提取
├── relation_extractor.py  # 关系提取
├── kg_quality.py          # 质量评估
├── kg_manager.py          # KG 管理器
├── llm_backend.py         # LLM 后端封装
├── document_converter.py  # 文档转换
├── data_processor.py      # 数据处理
└── chinese_prompts.py     # 中文提示词模板
```

---

## 相关文档

- [架构文档](../../../docs/architecture.md)
- [API 参考](../../../docs/api-reference.md)
- [配置参考](../../../docs/configuration.md)
- [测试策略](../../../docs/test-strategy.md)
