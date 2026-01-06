"""Tests for the DataProcessor component."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from epip.core.data_processor import DataProcessor, QualityReport


def test_prepare_documents_strips_whitespace(data_processor: DataProcessor) -> None:
    raw_documents = ["  alpha  ", "beta", "   gamma"]

    cleaned = data_processor.prepare_documents(raw_documents)

    assert cleaned == ["alpha", "beta", "gamma"]


def test_prepare_documents_ignores_empty_entries(data_processor: DataProcessor) -> None:
    raw_documents = ["", None, "delta"]  # type: ignore[list-item]

    cleaned = data_processor.prepare_documents(raw_documents)

    assert cleaned == ["delta"]


def test_scan_dataset_identifies_supported_files(tmp_path: Path) -> None:
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()
    csv_path = dataset_root / "sample.csv"
    csv_path.write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")

    pdf_path = dataset_root / "docs" / "dict.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    processor = DataProcessor(dataset_path=dataset_root, state_file=tmp_path / "state.json")

    files = processor.scan_dataset()

    assert len(files) == 2
    csv_info = next(f for f in files if f.file_type == "csv")
    assert csv_info.encoding is not None
    assert csv_info.file_hash
    assert any(f.file_type == "pdf" for f in files)


def test_detect_encoding_handles_utf8(tmp_path: Path) -> None:
    csv_path = tmp_path / "utf8.csv"
    csv_path.write_text("列,值\n甲,1\n乙,2\n", encoding="utf-8")
    processor = DataProcessor(dataset_path=tmp_path, state_file=tmp_path / "state.json")

    encoding = processor._detect_encoding(csv_path)

    assert encoding == "utf-8"


def test_preprocess_csv_handles_missing_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "raw.csv"
    csv_path.write_text("Name ,Value\nAlice,1\nBob,\nBob,\n", encoding="utf-8")
    processor = DataProcessor(dataset_path=tmp_path, state_file=tmp_path / "state.json")
    file_info = processor._get_file_info(csv_path)

    df = processor.preprocess_csv(file_info, missing_strategy="fill", fill_value=0)

    assert list(df.columns) == ["name", "value"]
    assert len(df) == 2  # duplicate Bob rows removed
    assert pd.api.types.is_numeric_dtype(df["value"])
    bob_value = df.loc[df["name"].str.lower() == "bob", "value"].iloc[0]
    assert int(bob_value) == 0


def test_generate_quality_report_creates_markdown(tmp_path: Path) -> None:
    processor = DataProcessor(dataset_path=tmp_path, state_file=tmp_path / "state.json")
    reports = [
        QualityReport(
            file_path="sample.csv",
            row_count=10,
            column_count=2,
            missing_rate=0.0,
            duplicate_rate=0.0,
            columns=["name", "value"],
        )
    ]

    output = processor.generate_quality_report(reports, output_path=tmp_path / "report.md")

    contents = output.read_text(encoding="utf-8")
    assert "数据质量报告" in contents
    assert "| sample.csv" in contents
