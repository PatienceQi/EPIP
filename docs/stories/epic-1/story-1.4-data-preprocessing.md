# Story 1.4: 数据预处理管道

**Epic**: Epic 1 - 基础设施与 Light-RAG 集成
**优先级**: P0
**估算**: 中型

---

## 用户故事

**作为** 数据工程师，
**我想要** 预处理 dataset/ 目录下的原始数据，
**以便** 为 Light-RAG 提供高质量的输入。

---

## 验收标准

### AC1: 文件扫描与识别
- [ ] 扫描 `dataset/` 目录及其子目录
- [ ] 识别所有 CSV 文件（24 个）
- [ ] 识别所有 PDF 文件（4 个数据字典）
- [ ] 输出文件清单（路径、大小、类型）

### AC2: CSV 编码处理
- [ ] 自动检测文件编码（UTF-8, GBK, Big5 等）
- [ ] 统一转换为 UTF-8 编码
- [ ] 处理编码转换错误

### AC3: 数据清洗
- [ ] 处理缺失值（配置化策略：删除/填充/标记）
- [ ] 标准化列名（移除空格、特殊字符）
- [ ] 处理重复行
- [ ] 数据类型推断和转换

### AC4: 数据质量报告
- [ ] 生成数据质量报告
- [ ] 统计：行数、列数、缺失率、重复率
- [ ] 输出 Markdown 格式报告

### AC5: 增量处理
- [ ] 基于文件哈希检测变更
- [ ] 跳过已处理的文件
- [ ] 记录处理状态

---

## 技术任务

### Task 1.4.1: 实现文件扫描器
```python
# src/epip/core/data_processor.py

from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import chardet
import structlog

logger = structlog.get_logger()

@dataclass
class FileInfo:
    """文件信息"""
    path: Path
    file_type: str  # csv, pdf
    size_bytes: int
    encoding: Optional[str] = None
    file_hash: Optional[str] = None

    @property
    def size_human(self) -> str:
        """人类可读的文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if self.size_bytes < 1024:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024
        return f"{self.size_bytes:.1f} TB"

@dataclass
class QualityReport:
    """数据质量报告"""
    file_path: str
    row_count: int
    column_count: int
    missing_rate: float
    duplicate_rate: float
    columns: List[str]
    issues: List[str] = field(default_factory=list)
    processed_at: datetime = field(default_factory=datetime.now)

class DataProcessor:
    """数据预处理器"""

    SUPPORTED_EXTENSIONS = {".csv", ".pdf"}

    def __init__(self, dataset_path: Path = Path("dataset")):
        self.dataset_path = dataset_path
        self.processed_hashes: set = set()

    def scan_dataset(self, path: Optional[Path] = None) -> List[FileInfo]:
        """扫描数据集目录"""
        scan_path = path or self.dataset_path
        files = []

        for file_path in scan_path.rglob("*"):
            if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                file_info = self._get_file_info(file_path)
                files.append(file_info)
                logger.debug("File found", path=str(file_path), type=file_info.file_type)

        logger.info(
            "Dataset scan complete",
            total_files=len(files),
            csv_count=sum(1 for f in files if f.file_type == "csv"),
            pdf_count=sum(1 for f in files if f.file_type == "pdf")
        )
        return files

    def _get_file_info(self, path: Path) -> FileInfo:
        """获取文件信息"""
        file_type = path.suffix.lower().lstrip(".")
        size = path.stat().st_size
        file_hash = self._compute_hash(path)

        encoding = None
        if file_type == "csv":
            encoding = self._detect_encoding(path)

        return FileInfo(
            path=path,
            file_type=file_type,
            size_bytes=size,
            encoding=encoding,
            file_hash=file_hash
        )

    def _compute_hash(self, path: Path) -> str:
        """计算文件哈希"""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _detect_encoding(self, path: Path) -> str:
        """检测文件编码"""
        with open(path, "rb") as f:
            raw = f.read(10000)
        result = chardet.detect(raw)
        return result["encoding"] or "utf-8"
```

### Task 1.4.2: 实现 CSV 预处理
```python
# src/epip/core/data_processor.py (续)

import pandas as pd
from typing import Dict, Any

class DataProcessor:
    # ... 上面的代码 ...

    def preprocess_csv(
        self,
        file_info: FileInfo,
        missing_strategy: str = "mark",  # drop, fill, mark
        fill_value: Any = None
    ) -> pd.DataFrame:
        """预处理 CSV 文件"""
        # 读取 CSV
        df = pd.read_csv(
            file_info.path,
            encoding=file_info.encoding,
            on_bad_lines="warn"
        )

        original_shape = df.shape
        logger.info("CSV loaded", path=str(file_info.path), shape=original_shape)

        # 标准化列名
        df.columns = self._normalize_column_names(df.columns)

        # 处理缺失值
        df = self._handle_missing_values(df, missing_strategy, fill_value)

        # 删除重复行
        df = df.drop_duplicates()

        # 数据类型推断
        df = self._infer_dtypes(df)

        logger.info(
            "CSV preprocessed",
            path=str(file_info.path),
            original_shape=original_shape,
            final_shape=df.shape
        )
        return df

    def _normalize_column_names(self, columns: pd.Index) -> pd.Index:
        """标准化列名"""
        return columns.str.strip().str.lower().str.replace(r"[^\w]", "_", regex=True)

    def _handle_missing_values(
        self,
        df: pd.DataFrame,
        strategy: str,
        fill_value: Any
    ) -> pd.DataFrame:
        """处理缺失值"""
        if strategy == "drop":
            return df.dropna()
        elif strategy == "fill":
            return df.fillna(fill_value if fill_value is not None else "N/A")
        elif strategy == "mark":
            # 添加缺失标记列
            df["_has_missing"] = df.isnull().any(axis=1)
            return df
        return df

    def _infer_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """推断数据类型"""
        for col in df.columns:
            # 尝试转换为数值
            try:
                df[col] = pd.to_numeric(df[col])
                continue
            except (ValueError, TypeError):
                pass

            # 尝试转换为日期
            try:
                df[col] = pd.to_datetime(df[col])
                continue
            except (ValueError, TypeError):
                pass

        return df

    def validate_data(self, df: pd.DataFrame, file_path: str) -> QualityReport:
        """验证数据质量"""
        row_count = len(df)
        column_count = len(df.columns)
        missing_rate = df.isnull().sum().sum() / (row_count * column_count)
        duplicate_rate = 1 - len(df.drop_duplicates()) / row_count if row_count > 0 else 0

        issues = []
        if missing_rate > 0.1:
            issues.append(f"High missing rate: {missing_rate:.1%}")
        if duplicate_rate > 0.05:
            issues.append(f"High duplicate rate: {duplicate_rate:.1%}")

        return QualityReport(
            file_path=file_path,
            row_count=row_count,
            column_count=column_count,
            missing_rate=missing_rate,
            duplicate_rate=duplicate_rate,
            columns=list(df.columns),
            issues=issues
        )
```

### Task 1.4.3: 实现质量报告生成
```python
# src/epip/core/data_processor.py (续)

class DataProcessor:
    # ... 上面的代码 ...

    def generate_quality_report(
        self,
        reports: List[QualityReport],
        output_path: Path = Path("data/quality_report.md")
    ) -> Path:
        """生成数据质量报告"""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# 数据质量报告",
            "",
            f"**生成时间**: {datetime.now().isoformat()}",
            f"**文件总数**: {len(reports)}",
            "",
            "## 概览",
            "",
            "| 文件 | 行数 | 列数 | 缺失率 | 重复率 | 问题 |",
            "|------|------|------|--------|--------|------|",
        ]

        total_rows = 0
        files_with_issues = 0

        for report in reports:
            total_rows += report.row_count
            if report.issues:
                files_with_issues += 1

            issues_str = "; ".join(report.issues) if report.issues else "无"
            lines.append(
                f"| {Path(report.file_path).name} "
                f"| {report.row_count:,} "
                f"| {report.column_count} "
                f"| {report.missing_rate:.1%} "
                f"| {report.duplicate_rate:.1%} "
                f"| {issues_str} |"
            )

        lines.extend([
            "",
            "## 统计",
            "",
            f"- 总行数: {total_rows:,}",
            f"- 有问题的文件: {files_with_issues}/{len(reports)}",
            "",
            "## 详细信息",
            "",
        ])

        for report in reports:
            lines.extend([
                f"### {Path(report.file_path).name}",
                "",
                f"- 路径: `{report.file_path}`",
                f"- 行数: {report.row_count:,}",
                f"- 列数: {report.column_count}",
                f"- 列名: {', '.join(report.columns[:10])}{'...' if len(report.columns) > 10 else ''}",
                "",
            ])

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Quality report generated", path=str(output_path))
        return output_path

    def is_processed(self, file_info: FileInfo) -> bool:
        """检查文件是否已处理"""
        return file_info.file_hash in self.processed_hashes

    def mark_processed(self, file_info: FileInfo):
        """标记文件已处理"""
        self.processed_hashes.add(file_info.file_hash)
```

### Task 1.4.4: 创建数据处理脚本
```python
# scripts/preprocess_data.py

import asyncio
from pathlib import Path
from epip.core.data_processor import DataProcessor, FileInfo, QualityReport

def main():
    """主数据预处理流程"""
    print("=" * 50)
    print("EPIP Data Preprocessing Pipeline")
    print("=" * 50)

    processor = DataProcessor(Path("dataset"))

    # 1. 扫描数据集
    print("\n[1] Scanning dataset...")
    files = processor.scan_dataset()

    csv_files = [f for f in files if f.file_type == "csv"]
    pdf_files = [f for f in files if f.file_type == "pdf"]

    print(f"    Found {len(csv_files)} CSV files")
    print(f"    Found {len(pdf_files)} PDF files")

    # 2. 预处理 CSV
    print("\n[2] Preprocessing CSV files...")
    reports = []

    for file_info in csv_files:
        if processor.is_processed(file_info):
            print(f"    [SKIP] {file_info.path.name} (already processed)")
            continue

        print(f"    Processing: {file_info.path.name}")
        try:
            df = processor.preprocess_csv(file_info)
            report = processor.validate_data(df, str(file_info.path))
            reports.append(report)
            processor.mark_processed(file_info)

            # 保存预处理结果
            output_path = Path("data/processed") / f"{file_info.path.stem}.parquet"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(output_path)

        except Exception as e:
            print(f"    [ERROR] {file_info.path.name}: {e}")

    # 3. 生成质量报告
    print("\n[3] Generating quality report...")
    report_path = processor.generate_quality_report(reports)
    print(f"    Report saved to: {report_path}")

    # 4. 总结
    print("\n" + "=" * 50)
    print("Preprocessing Complete")
    print("=" * 50)
    print(f"Processed: {len(reports)} files")
    print(f"Issues found: {sum(1 for r in reports if r.issues)}")

if __name__ == "__main__":
    main()
```

### Task 1.4.5: 更新依赖
```toml
# pyproject.toml 添加依赖
dependencies = [
    # ... 现有依赖 ...
    "chardet>=5.0",
    "pyarrow>=14.0",  # parquet 支持
]
```

---

## 测试用例

### 单元测试
- [ ] 测试 `scan_dataset()` 正确识别 CSV/PDF
- [ ] 测试 `_detect_encoding()` UTF-8/GBK/Big5
- [ ] 测试 `_normalize_column_names()` 各种情况
- [ ] 测试 `_handle_missing_values()` 三种策略
- [ ] 测试 `validate_data()` 质量指标计算
- [ ] 测试 `_compute_hash()` 一致性

### 集成测试
- [ ] 测试完整预处理流程（使用测试数据集）
- [ ] 测试增量处理（跳过已处理文件）
- [ ] 测试质量报告生成

### 验收测试
- [ ] 扫描 `dataset/` 识别 24 个 CSV + 4 个 PDF
- [ ] 所有 CSV 预处理成功
- [ ] 质量报告正确生成

---

## 依赖关系

- **前置**: Story 1.1（项目结构）
- **后置**: Epic 2（KG 构建需要预处理后的数据）

---

## 相关文档

- 架构: `docs/architecture.md` 5.1 节（DataProcessor 组件）
- 数据集: `dataset/` 目录
