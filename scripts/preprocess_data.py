"""Command line entry point for dataset preprocessing."""

from __future__ import annotations

from pathlib import Path

from epip.core.data_processor import DataProcessor


def main() -> None:
    """Execute the preprocessing workflow."""
    print("=" * 60)
    print("EPIP Data Preprocessing Pipeline")
    print("=" * 60)

    processor = DataProcessor(Path("dataset"))

    print("\n[1] Scanning dataset...")
    files = processor.scan_dataset()
    csv_files = [f for f in files if f.file_type == "csv"]
    pdf_files = [f for f in files if f.file_type == "pdf"]
    print(f"    Found {len(csv_files)} CSV files")
    print(f"    Found {len(pdf_files)} PDF files")

    print("\n[2] Preprocessing CSV files...")
    reports = []
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)

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

            output_path = processed_dir / f"{file_info.path.stem}.parquet"
            df.to_parquet(output_path, index=False)
            print(f"        Saved to {output_path}")
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"    [ERROR] {file_info.path.name}: {exc}")

    print("\n[3] Generating quality report...")
    report_path = processor.generate_quality_report(
        reports, output_path=Path("data/quality_report.md")
    )
    print(f"    Report saved to: {report_path}")

    print("\n" + "=" * 60)
    print("Preprocessing Complete")
    print("=" * 60)
    print(f"Processed: {len(reports)} files")
    print(f"Issues found: {sum(1 for r in reports if r.issues)}")


if __name__ == "__main__":
    main()
