"""Data preprocessing utilities for EPIP pipelines."""

from __future__ import annotations

import hashlib
import json
import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import chardet
import pandas as pd
import structlog

logger = structlog.get_logger()


@dataclass
class FileInfo:
    """Metadata about a dataset file."""

    path: Path
    file_type: str
    size_bytes: int
    encoding: str | None = None
    file_hash: str | None = None

    @property
    def size_human(self) -> str:
        """Return human readable file size."""
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


@dataclass
class QualityReport:
    """Summary of a processed file."""

    file_path: str
    row_count: int
    column_count: int
    missing_rate: float
    duplicate_rate: float
    columns: list[str]
    issues: list[str] = field(default_factory=list)
    processed_at: datetime = field(default_factory=datetime.now)


class DataProcessor:
    """Data preparation pipeline for the EPIP datasets."""

    SUPPORTED_EXTENSIONS = {".csv", ".pdf"}

    def __init__(
        self,
        dataset_path: Path = Path("dataset"),
        state_file: Path | None = None,
    ):
        self.dataset_path = dataset_path
        self.state_file = state_file or Path("data/.processed_files.json")
        self.processed_hashes: set[str] = self._load_processed_hashes()

    def prepare_documents(self, raw_documents: Iterable[str]) -> list[str]:
        """Normalize raw textual documents (used by query pipeline)."""
        cleaned: list[str] = []
        for document in raw_documents:
            if not document:
                continue
            cleaned.append(document.strip())
        return cleaned

    def scan_dataset(self, path: Path | None = None) -> list[FileInfo]:
        """Scan dataset directory and collect FileInfo objects."""
        scan_path = path or self.dataset_path
        if not scan_path.exists():
            logger.warning("Dataset path not found", path=str(scan_path))
            return []

        files: list[FileInfo] = []
        for file_path in sorted(scan_path.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue
            file_info = self._get_file_info(file_path)
            files.append(file_info)
            logger.debug(
                "File discovered",
                path=str(file_path),
                type=file_info.file_type,
                size=file_info.size_bytes,
            )

        logger.info(
            "Dataset scan complete",
            total_files=len(files),
            csv_count=sum(1 for f in files if f.file_type == "csv"),
            pdf_count=sum(1 for f in files if f.file_type == "pdf"),
        )
        return files

    def _get_file_info(self, path: Path) -> FileInfo:
        file_type = path.suffix.lower().lstrip(".")
        size = path.stat().st_size
        file_hash = self._compute_hash(path)
        encoding: str | None = None
        if file_type == "csv":
            encoding = self._detect_encoding(path)
        return FileInfo(
            path=path,
            file_type=file_type,
            size_bytes=size,
            encoding=encoding,
            file_hash=file_hash,
        )

    def _load_processed_hashes(self) -> set[str]:
        if not self.state_file.exists():
            return set()
        try:
            raw = self.state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, list):
                return {str(item) for item in data}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load processed cache",
                path=str(self.state_file),
                error=str(exc),
            )
        return set()

    def _persist_processed_hashes(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(sorted(self.processed_hashes))
        self.state_file.write_text(payload, encoding="utf-8")

    def _detect_encoding(self, path: Path) -> str:
        """Detect file encoding using chardet."""
        with path.open("rb") as handle:
            raw = handle.read(10000)
        if not raw:
            return "utf-8"
        result = chardet.detect(raw)
        encoding = result.get("encoding") or "utf-8"
        return encoding.lower()

    def _compute_hash(self, path: Path) -> str:
        """Compute MD5 hash of a file."""
        hasher = hashlib.md5()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def preprocess_csv(
        self,
        file_info: FileInfo,
        missing_strategy: str = "mark",
        fill_value: Any = None,
    ) -> pd.DataFrame:
        """Load and clean a CSV file."""
        if file_info.file_type != "csv":
            raise ValueError("preprocess_csv only supports CSV files")

        encoding = file_info.encoding or self._detect_encoding(file_info.path)
        df = pd.read_csv(
            file_info.path,
            encoding=encoding,
            on_bad_lines="warn",
        )
        original_shape = df.shape

        df.columns = self._normalize_column_names(df.columns)
        df = self._handle_missing_values(df, missing_strategy, fill_value)
        df = df.drop_duplicates()
        df = self._infer_dtypes(df)

        logger.info(
            "CSV preprocessed",
            path=str(file_info.path),
            original_shape=original_shape,
            final_shape=df.shape,
        )
        return df

    def _normalize_column_names(self, columns: pd.Index | Iterable[str]) -> pd.Index:
        """Normalize column names by stripping spaces and special chars."""
        if not isinstance(columns, pd.Index):
            columns = pd.Index(columns)

        normalized = (
            columns.astype(str)
            .str.strip()
            .str.lower()
            .str.replace(r"[^\w]+", "_", regex=True)
            .str.strip("_")
        )
        normalized = normalized.where(normalized != "", "column")

        unique_columns: list[str] = []
        counter: dict[str, int] = {}
        for name in normalized:
            base = name
            count = counter.get(base, 0)
            new_name = base if count == 0 else f"{base}_{count}"
            counter[base] = count + 1
            unique_columns.append(new_name)
        return pd.Index(unique_columns)

    def _handle_missing_values(
        self,
        df: pd.DataFrame,
        strategy: str,
        fill_value: Any,
    ) -> pd.DataFrame:
        """Handle missing values based on strategy."""
        if strategy == "drop":
            return df.dropna()
        if strategy == "fill":
            value = "N/A" if fill_value is None else fill_value
            return df.fillna(value)
        if strategy == "mark":
            df = df.copy()
            df["_has_missing"] = df.isnull().any(axis=1)
            return df
        raise ValueError(f"Unsupported missing value strategy: {strategy}")

    def _infer_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Attempt to convert columns to numeric or datetime types."""
        for column in df.columns:
            series = df[column]
            if series.dtype.kind in {"b"}:
                continue
            try:
                converted = pd.to_numeric(series, errors="raise")
                df[column] = converted
                continue
            except (ValueError, TypeError):
                pass
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=UserWarning)
                    converted = pd.to_datetime(series, errors="raise")
                df[column] = converted
            except (ValueError, TypeError):
                continue
        return df

    def validate_data(self, df: pd.DataFrame, file_path: str) -> QualityReport:
        """Run basic data quality checks and return report."""
        row_count = len(df)
        column_count = len(df.columns)
        total_cells = row_count * column_count
        missing_rate = float(df.isnull().sum().sum()) / total_cells if total_cells else 0.0
        duplicate_rate = 1 - (len(df.drop_duplicates()) / row_count) if row_count else 0.0

        issues: list[str] = []
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
            issues=issues,
        )

    def generate_quality_report(
        self,
        reports: list[QualityReport],
        output_path: Path = Path("data/quality_report.md"),
    ) -> Path:
        """Render a Markdown data quality report."""
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

        lines.extend(
            [
                "",
                "## 统计",
                "",
                f"- 总行数: {total_rows:,}",
                f"- 有问题的文件: {files_with_issues}/{len(reports)}",
                "",
                "## 详细信息",
                "",
            ]
        )

        for report in reports:
            column_preview = ", ".join(report.columns[:10])
            if len(report.columns) > 10:
                column_preview += "..."
            lines.extend(
                [
                    f"### {Path(report.file_path).name}",
                    "",
                    f"- 路径: `{report.file_path}`",
                    f"- 行数: {report.row_count:,}",
                    f"- 列数: {report.column_count}",
                    f"- 缺失率: {report.missing_rate:.1%}",
                    f"- 重复率: {report.duplicate_rate:.1%}",
                    f"- 列名: {column_preview}",
                    "",
                ]
            )

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Quality report generated", path=str(output_path))
        return output_path

    def is_processed(self, file_info: FileInfo) -> bool:
        """Return True if file hash already processed."""
        return file_info.file_hash in self.processed_hashes

    def mark_processed(self, file_info: FileInfo) -> None:
        """Record that a file has been processed."""
        if not file_info.file_hash:
            return
        self.processed_hashes.add(file_info.file_hash)
        self._persist_processed_hashes()
