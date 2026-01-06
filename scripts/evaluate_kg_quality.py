"""Evaluate KG quality metrics and export structured reports."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import structlog

from epip.config import LightRAGConfig, QualitySettings
from epip.core.kg_builder import KGBuilder
from epip.core.kg_quality import (
    KGQualityEvaluator,
    KGQualityReport,
    QualityReportGenerator,
    QualityThresholds,
)

logger = structlog.get_logger()


def _build_parser(defaults: QualitySettings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate knowledge graph quality against expectations"
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path(defaults.ground_truth_path),
        help="Path to expected KG definition (YAML/JSON)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(defaults.markdown_report),
        help="Path to export the Markdown summary",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path(defaults.json_report),
        help="Path to export the JSON payload",
    )
    parser.add_argument(
        "--threshold-file",
        type=Path,
        default=None,
        help="Optional path to override default quality thresholds",
    )
    return parser


def _parse_args(defaults: QualitySettings) -> argparse.Namespace:
    parser = _build_parser(defaults)
    return parser.parse_args()


def _resolve_thresholds(
    threshold_file: Path | None,
    defaults: QualitySettings,
) -> QualityThresholds:
    if threshold_file is not None:
        if threshold_file.exists():
            return QualityThresholds.from_file(threshold_file)
        logger.warning(
            "Threshold override file missing; falling back to defaults",
            path=str(threshold_file),
        )
    return defaults.as_thresholds()


async def _execute(
    args: argparse.Namespace,
    defaults: QualitySettings | None = None,
) -> KGQualityReport:
    defaults = defaults or QualitySettings()
    thresholds = _resolve_thresholds(args.threshold_file, defaults)
    evaluator = KGQualityEvaluator(
        ground_truth_path=args.ground_truth,
        thresholds=thresholds,
    )
    builder = KGBuilder(config=LightRAGConfig())
    presenter = QualityReportGenerator()

    print("=" * 60)
    print("EPIP KG Quality Evaluation")
    print("=" * 60)

    report = await evaluator.generate_report(builder)
    markdown_path = evaluator.export_markdown(report, args.report)
    json_path = evaluator.export_json(report, args.json)

    print("[Scores]")
    print(presenter.generate_ascii_chart(report.score_breakdown))
    print(f"Overall score: {report.overall_score:.2f}")
    print(f"Markdown exported to: {markdown_path}")
    print(f"JSON exported to: {json_path}")

    if report.issues:
        print("\n[Issues]")
        for issue in report.issues:
            print(f"- {issue}")
    else:
        print("\nNo blocking issues detected.")

    print("=" * 60)
    return report


async def main() -> None:
    defaults = QualitySettings()
    args = _parse_args(defaults)
    try:
        report = await _execute(args, defaults)
    except Exception as exc:  # pragma: no cover - CLI level logging
        logger.exception("KG quality evaluation failed", error=str(exc))
        raise
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
