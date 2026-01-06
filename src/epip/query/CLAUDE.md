[根目录](../../../CLAUDE.md) > [src](../../) > [epip](../) > **query**

# query - 查询解析与执行

> 最后更新：2026-01-06T19:49:12+0800

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

将自然语言查询转换为结构化表示，生成 Cypher 查询语句，执行图数据库检索，并提供实体链接与查询规划能力。

核心能力：
- 自然语言查询解析（LLM + 启发式规则）
- 意图分类（事实查询、关系查询、路径查询、聚合、对比）
- 实体提取与类型识别
- Cypher 查询生成与参数化
- 查询执行与结果转换
- 实体链接（模糊匹配、消歧）

---

## 入口与启动

### 主要文件

- `parser.py` - 自然语言查询解析器
- `cypher.py` - Cypher 查询生成器
- `executor.py` - 查询执行引擎
- `linker.py` - 实体链接器
- `planner.py` - 查询规划器
- `algorithms.py` - 图算法封装（最短路径、社区发现等）

### 初始化示例

```python
from epip.query.parser import QueryParser
from epip.query.cypher import CypherGenerator
from epip.query.executor import QueryExecutor
from epip.core.llm_backend import create_llm_backend
from epip.config import LightRAGConfig

config = LightRAGConfig()
backend = create_llm_backend(config)

# 查询解析器
parser = QueryParser(backend=backend, config=config)

# Cypher 生成器
cypher_gen = CypherGenerator()

# 查询执行器
executor = QueryExecutor(neo4j_client=neo4j_client)

# 完整流程
parsed = await parser.parse("2023年有哪些政策支持女性创业？")
cypher_query = cypher_gen.generate(parsed)
results = await executor.execute(cypher_query)
```

---

## 对外接口

### QueryParser

**核心方法**：
- `parse(query: str) -> ParsedQuery` - 解析自然语言查询
- `extract_entities(query: str) -> list[EntityMention]` - 提取实体
- `classify_intent(query: str) -> QueryIntent` - 分类查询意图

**支持的意图类型**：
- `FACT` - 事实查询（默认）
- `RELATION` - 关系查询
- `PATH` - 路径查询
- `AGGREGATE` - 聚合统计
- `COMPARE` - 对比分析

### ParsedQuery

```python
@dataclass
class ParsedQuery:
    original: str                        # 原始查询文本
    intent: QueryIntent                  # 查询意图
    entities: list[EntityMention]        # 实体提及列表
    constraints: list[QueryConstraint]   # 约束条件
    complexity: int                      # 复杂度评分（1-5）
```

### EntityMention

```python
@dataclass
class EntityMention:
    text: str                # 实体文本
    entity_type: str | None  # 实体类型（ORGANIZATION、ENTITY 等）
    start: int               # 起始位置
    end: int                 # 结束位置
```

### QueryConstraint

```python
@dataclass
class QueryConstraint:
    field: str               # 字段名（time、location、demographic 等）
    operator: str            # 操作符（=、in、between 等）
    value: ConstraintValue   # 约束值
```

---

## 关键依赖与配置

### 依赖项

- `epip.core.llm_backend` - LLM 后端（用于查询解析）
- `epip.config` - 配置管理
- `structlog` - 结构化日志

### 配置参数

- `system_prompt` - LLM 系统提示词（默认提供 JSON Schema）
- `cache_size` - 查询解析缓存大小（默认 32）
- `max_tokens` - LLM 最大生成 token 数（默认 600）
- `temperature` - LLM 温度参数（默认 0.0，确保稳定输出）

### 启发式规则

当 LLM 不可用或解析失败时，使用以下规则：
- **实体识别**：大写单词序列、中文连续字符（≥2 字）
- **时间约束**：年份模式（`2020`）、范围模式（`between 2020 and 2023`）
- **位置约束**：`in/within` 后跟大写地名
- **人口统计**：关键词匹配（`女性`/`women`、`男性`/`men`）
- **意图猜测**：关键词匹配（`compare`/`对比` → COMPARE，`路径` → PATH）

---

## 数据模型

### 查询复杂度评分

基于以下因素计算（1-5 分）：
- 查询长度（>12 词 +1）
- 实体数量（>1 个 +1）
- 约束数量（>1 个 +1）
- 意图类型（AGGREGATE/COMPARE/PATH +1）

### 缓存机制

- 使用 `OrderedDict` 实现 LRU 缓存
- 缓存键：原始查询文本
- 缓存值：LLM 返回的 JSON payload
- 缓存大小可配置（默认 32 条）

---

## 测试与质量

### 测试文件

- `tests/unit/test_query_engine.py` - 单元测试（解析器、生成器、执行器）

### 测试覆盖

- 自然语言查询解析（中英文）
- 意图分类准确性
- 实体提取与边界检测
- 约束条件解析
- 启发式规则回退
- 缓存命中与失效
- 异常处理与降级

---

## 常见问题 (FAQ)

**Q: 如何提高实体识别准确率？**
A: 1) 调整 LLM 系统提示词；2) 扩展启发式规则；3) 集成实体链接器（`linker.py`）。

**Q: 查询解析失败怎么办？**
A: 解析器会自动回退到启发式规则，返回基于模式匹配的结果。检查日志确认回退原因。

**Q: 如何支持新的查询意图？**
A: 1) 在 `QueryIntent` 枚举中添加新类型；2) 更新系统提示词；3) 扩展 `_guess_intent()` 启发式规则。

**Q: 复杂度评分有什么用？**
A: 用于查询规划与资源分配，高复杂度查询可能触发分解策略（见 `epip.reasoning.decomposer`）。

**Q: 如何调试 LLM 解析输出？**
A: 启用 DEBUG 日志级别，查看 `_parse_llm_payload()` 的原始输出与解析结果。

---

## 相关文件清单

```
src/epip/query/
├── parser.py          # 自然语言查询解析器（362 行）
├── cypher.py          # Cypher 查询生成器
├── executor.py        # 查询执行引擎
├── linker.py          # 实体链接器
├── planner.py         # 查询规划器
├── algorithms.py      # 图算法封装
└── __init__.py        # 模块导出
```

---

## 下一步建议

- 补充 Cypher 生成器文档与示例
- 实现查询优化器（索引提示、查询重写）
- 扩展实体链接器支持模糊匹配与消歧
- 添加查询模板库（常见查询模式）
- 集成查询性能分析（EXPLAIN/PROFILE）
