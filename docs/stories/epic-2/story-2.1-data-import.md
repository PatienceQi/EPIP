# Story 2.1: Light-RAG 数据导入（CSV + PDF）

**Epic**: Epic 2 - 知识图谱构建与优化
**优先级**: P0
**估算**: 中型

---

## 用户故事

**作为** 数据工程师，
**我想要** 使用 Light-RAG 导入 CSV 和 PDF 数据，
**以便** 自动构建初始知识图谱。

---

## 验收标准

### AC1: CSV 数据导入
- [ ] 读取 `data/processed/*.parquet` 预处理后的数据
- [ ] 将 DataFrame 转换为 Light-RAG 可接受的文本格式
- [ ] 批量调用 Light-RAG 的 `insert()` 方法导入
- [ ] 处理导入错误并记录

### AC2: PDF 数据字典导入
- [ ] 识别 `dataset/` 目录下的 PDF 文件
- [ ] 使用 pypdf 或 pdfplumber 提取 PDF 文本
- [ ] 将提取的文本导入 Light-RAG
- [ ] 记录 PDF 处理状态

### AC3: 分块策略配置
- [ ] 配置 Light-RAG chunk_size（默认 1200）
- [ ] 配置 chunk_overlap（默认 100）
- [ ] CSV 使用行级分块（每行/多行为一个 chunk）
- [ ] PDF 使用语义分块（段落级别）

### AC4: Neo4j 数据验证
- [ ] 验证实体节点已创建
- [ ] 验证关系边已创建
- [ ] 输出图统计信息

### AC5: 导入统计与报告
- [ ] 统计导入文件数
- [ ] 统计生成实体数
- [ ] 统计生成关系数
- [ ] 输出导入摘要报告

---

## 技术任务

### Task 2.1.1: 实现数据转换器
```python
# src/epip/core/document_converter.py

from pathlib import Path
import pandas as pd
from typing import Iterator

class DocumentConverter:
    """将各种数据格式转换为 Light-RAG 文档"""

    def parquet_to_documents(self, path: Path) -> Iterator[str]:
        """将 parquet 文件转换为文档字符串"""
        df = pd.read_parquet(path)
        # 行级分块：每行转为一个文档
        for idx, row in df.iterrows():
            doc = self._row_to_document(row, path.stem)
            yield doc

    def _row_to_document(self, row: pd.Series, source: str) -> str:
        """将 DataFrame 行转为文档"""
        lines = [f"Source: {source}"]
        for col, val in row.items():
            if pd.notna(val):
                lines.append(f"{col}: {val}")
        return "\n".join(lines)

    def pdf_to_documents(self, path: Path) -> Iterator[str]:
        """将 PDF 文件转换为文档字符串"""
        import pypdf
        reader = pypdf.PdfReader(path)
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                yield f"Source: {path.name} (Page {page_num + 1})\n\n{text}"
```

### Task 2.1.2: 扩展 KGBuilder
```python
# src/epip/core/kg_builder.py 扩展

class KGBuilder:
    # ... 现有代码 ...

    async def insert_from_parquet(
        self,
        parquet_files: Sequence[Path],
        batch_size: int = 50
    ) -> InsertResult:
        """从 parquet 文件批量导入"""
        converter = DocumentConverter()
        all_docs = []
        for pq_file in parquet_files:
            docs = list(converter.parquet_to_documents(pq_file))
            all_docs.extend(docs)

        # 批量插入
        return await self.insert_documents(all_docs, batch_size)

    async def insert_from_pdf(
        self,
        pdf_files: Sequence[Path]
    ) -> InsertResult:
        """从 PDF 文件导入"""
        converter = DocumentConverter()
        all_docs = []
        for pdf_file in pdf_files:
            docs = list(converter.pdf_to_documents(pdf_file))
            all_docs.extend(docs)

        return await self.insert_documents(all_docs)
```

### Task 2.1.3: 创建导入脚本
```python
# scripts/import_data.py

import asyncio
from pathlib import Path
from epip.core.kg_builder import KGBuilder
from epip.config import LightRAGConfig

async def main():
    config = LightRAGConfig()
    builder = KGBuilder(config)

    # 1. 导入 CSV (parquet)
    parquet_dir = Path("data/processed")
    parquet_files = list(parquet_dir.glob("*.parquet"))
    print(f"Found {len(parquet_files)} parquet files")

    csv_result = await builder.insert_from_parquet(parquet_files)
    print(f"CSV Import: {csv_result}")

    # 2. 导入 PDF
    pdf_dir = Path("dataset")
    pdf_files = list(pdf_dir.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")

    pdf_result = await builder.insert_from_pdf(pdf_files)
    print(f"PDF Import: {pdf_result}")

    # 3. 输出统计
    stats = await builder.get_statistics()
    print(f"\nKG Statistics:")
    print(f"  Entities: {stats.total_entities}")
    print(f"  Relations: {stats.total_relations}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Task 2.1.4: 更新依赖
```toml
# pyproject.toml 添加
dependencies = [
    # ... 现有 ...
    "pypdf>=4.0",  # PDF 解析
]
```

---

## 测试用例

### 单元测试
- [ ] 测试 `parquet_to_documents()` 正确转换
- [ ] 测试 `pdf_to_documents()` 正确提取
- [ ] 测试 `_row_to_document()` 格式化

### 集成测试
- [ ] 测试完整 parquet 导入流程（mock LightRAG）
- [ ] 测试完整 PDF 导入流程（mock LightRAG）
- [ ] 测试导入统计计算

### 验收测试
- [ ] 导入所有 23 个 parquet 文件
- [ ] 导入 4 个 PDF 数据字典
- [ ] Neo4j 中可查询到实体和关系

---

## 依赖关系

- **前置**: Story 1.4（需要预处理后的 parquet 文件）
- **后置**: Story 2.2（实体识别与消歧）

---

## 相关文档

- 架构: `docs/architecture.md` 5.2 节（KGBuilder 组件）
- Light-RAG: `src/epip/core/kg_builder.py`
- 预处理数据: `data/processed/*.parquet`
