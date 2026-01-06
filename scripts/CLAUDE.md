[根目录](../CLAUDE.md) > **scripts**

# 脚本工具模块 (Scripts)

> 最后更新：2026-01-06T19:33:46+0800

---

## 变更记录 (Changelog)

| 日期 | 版本 | 描述 |
|------|------|------|
| 2026-01-06 | 1.0.0 | 初始化模块文档 |

---

## 模块职责

CLI 工具集，提供数据导入、质量评估、基准测试等功能。

核心能力：
- **数据导入**：批量导入文档到知识图谱
- **质量评估**：评估 KG 质量指标
- **基准测试**：性能测试与优化
- **关系分析**：分析实体关系分布
- **实体评估**：评估实体提取质量

---

## 入口与启动

主要脚本：
- `import_data.py`：数据导入工具
- `kg_cli.py`：KG 管理 CLI
- `query_cli.py`：查询 CLI
- `evaluate_kg_quality.py`：质量评估
- `benchmark_performance.py`：性能基准测试
- `analyze_relations.py`：关系分析

---

## 对外接口

### 数据导入

```bash
# 查看导入状态
python scripts/import_data.py --status

# 开始导入（支持断点续传）
python scripts/import_data.py

# 自定义参数
python scripts/import_data.py --timeout 900 --max-retries 3 --cooldown 5

# 重试失败文件
python scripts/import_data.py --retry-failed
```

特性：
- 断点续传：进度自动保存，中断后可继续
- 错误重试：单文件最多重试 5 次，指数退避
- 中断安全：Ctrl+C 安全退出

### KG 管理

```bash
# 构建知识图谱
python scripts/kg_cli.py build --input data/documents/

# 查询实体
python scripts/kg_cli.py query --entity "政策名称"

# 导出图数据
python scripts/kg_cli.py export --format json --output data/export/
```

### 质量评估

```bash
# 评估 KG 质量
python scripts/evaluate_kg_quality.py

# 生成质量报告
python scripts/evaluate_kg_quality.py --report data/reports/kg_quality.md
```

### 性能基准测试

```bash
# 运行基准测试
python scripts/benchmark_performance.py

# 自定义测试参数
python scripts/benchmark_performance.py --queries 100 --concurrency 10
```

---

## 关键依赖与配置

### 依赖

- `click`：CLI 框架
- `tqdm`：进度条
- `pyyaml`：配置文件解析
- `pandas`：数据处理

### 配置

通过环境变量或配置文件：
- `.env`：环境变量配置
- `data/ground_truth/expected_kg.yaml`：质量评估基准

---

## 数据模型

### ImportProgress

```python
@dataclass
class ImportProgress:
    total_files: int
    processed_files: int
    failed_files: list[str]
    last_checkpoint: str
```

### QualityReport

```python
@dataclass
class QualityReport:
    entity_precision: float
    entity_recall: float
    relation_coverage: float
    graph_density: float
    avg_degree: float
    isolated_ratio: float
```

---

## 测试与质量

### 单元测试

- `tests/unit/test_kg_cli.py`：KG CLI 测试
- `tests/unit/test_kg_quality_script.py`：质量评估脚本测试
- `tests/unit/test_query_benchmark.py`：基准测试脚本测试

---

## 常见问题 (FAQ)

**Q: 导入失败如何处理？**
A: 查看 `data/lightrag/import_progress.json`，运行 `--retry-failed` 重试。

**Q: 如何自定义质量阈值？**
A: 修改 `.env` 中的 `QUALITY_*` 环境变量。

**Q: 如何优化导入性能？**
A: 调整 `--max-concurrent-llm` 和 `--max-concurrent-embed` 参数。

**Q: 如何导出图数据？**
A: 使用 `kg_cli.py export` 命令，支持 JSON、CSV、GraphML 格式。

---

## 相关文件清单

```
scripts/
├── __init__.py
├── import_data.py           # 数据导入工具
├── kg_cli.py                # KG 管理 CLI
├── query_cli.py             # 查询 CLI
├── evaluate_kg_quality.py   # 质量评估
├── benchmark_performance.py # 性能基准测试
├── analyze_relations.py     # 关系分析
├── evaluate_entities.py     # 实体评估
├── preprocess_data.py       # 数据预处理
├── run_benchmark.py         # 基准测试运行器
├── validate_quality.py      # 质量验证
└── verify_lightrag.py       # Light-RAG 验证
```

---

## 相关文档

- [架构文档](../docs/architecture.md)
- [配置参考](../docs/configuration.md)
- [测试策略](../docs/test-strategy.md)
