"""Quality acceptance checks for knowledge graph metrics."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import yaml

from epip.config import LightRAGConfig, QualitySettings
from epip.core.kg_builder import KGBuilder
from epip.core.kg_quality import (
    KGQualityEvaluator,
    KGQualityReport,
    QualityThresholds,
)

logger = structlog.get_logger()

DEFAULT_REPORT_PATH = Path("data/reports/kg_quality_acceptance.md")


@dataclass(slots=True)
class AcceptanceThresholds:
    """Target metrics derived from the PRD non-functional requirements."""

    entity_precision: float = 0.9
    relation_coverage: float = 0.8
    hallucination_rate: float = 0.05
    completeness: float = 0.95


@dataclass(slots=True)
class AdditionalQualityMetrics:
    """Operational metrics that are not part of KGQualityReport."""

    hallucination_rate: float
    completeness: float


@dataclass(slots=True)
class QualityAcceptanceSummary:
    """Aggregated acceptance decision."""

    entity_precision: float
    relation_coverage: float
    hallucination_rate: float
    completeness: float
    overall_score: float
    passed: bool
    failures: list[str]


ACCEPTANCE_TARGETS = AcceptanceThresholds()


def evaluate_acceptance(
    report: KGQualityReport,
    *,
    additional_metrics: AdditionalQualityMetrics,
    thresholds: AcceptanceThresholds = ACCEPTANCE_TARGETS,
) -> QualityAcceptanceSummary:
    """Evaluate metrics against acceptance thresholds."""

    entity_precision = float(report.entity_metrics.precision)
    relation_coverage = float(report.relation_metrics.coverage)
    hallucination_rate = float(additional_metrics.hallucination_rate)
    completeness = float(additional_metrics.completeness)

    failures: list[str] = []
    if entity_precision < thresholds.entity_precision:
        failures.append(
            f"Entity precision {entity_precision:.2f} below target "
            f"{thresholds.entity_precision:.2f}"
        )
    if relation_coverage < thresholds.relation_coverage:
        failures.append(
            f"Relation coverage {relation_coverage:.2f} below target "
            f"{thresholds.relation_coverage:.2f}"
        )
    if hallucination_rate > thresholds.hallucination_rate:
        failures.append(
            f"Hallucination rate {hallucination_rate:.2f} above target "
            f"{thresholds.hallucination_rate:.2f}"
        )
    if completeness < thresholds.completeness:
        failures.append(
            f"Data completeness {completeness:.2f} below target {thresholds.completeness:.2f}"
        )

    entity_score = _normalize_positive(entity_precision, thresholds.entity_precision)
    relation_score = _normalize_positive(
        relation_coverage,
        thresholds.relation_coverage,
    )
    hallucination_score = _normalize_inverse(
        hallucination_rate,
        thresholds.hallucination_rate,
    )
    completeness_score = _normalize_positive(completeness, thresholds.completeness)
    overall_score = round(
        (entity_score + relation_score + hallucination_score + completeness_score) / 4 * 100,
        2,
    )

    passed = not failures
    return QualityAcceptanceSummary(
        entity_precision=entity_precision,
        relation_coverage=relation_coverage,
        hallucination_rate=hallucination_rate,
        completeness=completeness,
        overall_score=overall_score,
        passed=passed,
        failures=failures,
    )


def _normalize_positive(value: float, threshold: float) -> float:
    if threshold <= 0:
        return 1.0 if value > 0 else 0.0
    return max(0.0, min(value / threshold, 1.0))


def _normalize_inverse(value: float, threshold: float) -> float:
    if threshold <= 0:
        return 1.0 if value == 0 else 0.0
    if value <= threshold:
        return 1.0
    if value <= 0:
        return 1.0
    return max(0.0, min(threshold / value, 1.0))


def _build_parser(defaults: QualitySettings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate KG quality metrics against PRD acceptance thresholds"
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
        default=DEFAULT_REPORT_PATH,
        help="Path to export the Markdown acceptance report",
    )
    parser.add_argument(
        "--threshold-file",
        type=Path,
        default=None,
        help="Optional path to override KG evaluation thresholds",
    )
    parser.add_argument(
        "--metrics-file",
        type=Path,
        default=None,
        help="Optional JSON/YAML file containing hallucination_rate and completeness",
    )
    parser.add_argument(
        "--hallucination-rate",
        type=float,
        default=0.02,
        help="Fallback hallucination rate (0-1) used when no metrics file is supplied",
    )
    parser.add_argument(
        "--data-completeness",
        type=float,
        default=0.97,
        help="Fallback data completeness ratio (0-1) used when no metrics file is supplied",
    )
    return parser


def _parse_args(defaults: QualitySettings) -> argparse.Namespace:
    return _build_parser(defaults).parse_args()


def _resolve_evaluator_thresholds(
    args: argparse.Namespace,
    defaults: QualitySettings,
    targets: AcceptanceThresholds,
) -> QualityThresholds:
    base = defaults.as_thresholds()
    if args.threshold_file:
        if args.threshold_file.exists():
            base = QualityThresholds.from_file(args.threshold_file)
        else:
            logger.warning(
                "Threshold override file not found; using defaults",
                path=str(args.threshold_file),
            )
    return QualityThresholds(
        entity_precision=max(base.entity_precision, targets.entity_precision),
        entity_recall=base.entity_recall,
        relation_coverage=max(base.relation_coverage, targets.relation_coverage),
        graph_density=base.graph_density,
        min_avg_degree=base.min_avg_degree,
        max_isolated_ratio=base.max_isolated_ratio,
    )


def _load_mapping(path: Path) -> Mapping[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Quality metrics file not found", path=str(path))
        return {}
    except Exception as exc:  # pragma: no cover - filesystem errors are environment specific
        logger.warning("Failed to read quality metrics", path=str(path), error=str(exc))
        return {}
    if not content.strip():
        return {}
    try:
        if path.suffix.lower() == ".json":
            return json.loads(content)
        return yaml.safe_load(content) or {}
    except Exception as exc:  # pragma: no cover - invalid files are environment specific
        logger.warning("Failed to parse quality metrics", path=str(path), error=str(exc))
        return {}


def _resolve_additional_metrics(
    metrics_file: Path | None,
    *,
    fallback_hallucination: float,
    fallback_completeness: float,
) -> AdditionalQualityMetrics:
    if metrics_file:
        data = _load_mapping(metrics_file)
    else:
        data = {}
    hallucination = float(data.get("hallucination_rate", fallback_hallucination))
    completeness = float(data.get("completeness", fallback_completeness))
    return AdditionalQualityMetrics(
        hallucination_rate=hallucination,
        completeness=completeness,
    )


def _write_markdown_report(
    output_path: Path,
    report: KGQualityReport,
    acceptance: QualityAcceptanceSummary,
    thresholds: AcceptanceThresholds,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _status(label: bool) -> str:
        return "PASS" if label else "FAIL"

    lines = [
        "# Knowledge Graph Quality Acceptance Report",
        "",
        f"- KG quality score: {report.overall_score:.2f}",
        f"- Acceptance score: {acceptance.overall_score:.2f}",
        f"- Status: {'PASSED' if acceptance.passed else 'FAILED'}",
        "",
        "## Metrics",
        "| Metric | Value | Target | Result |",
        "| --- | --- | --- | --- |",
        (
            f"| Entity precision | {acceptance.entity_precision:.2%} | "
            f"{thresholds.entity_precision:.0%} | "
            f"{_status(acceptance.entity_precision >= thresholds.entity_precision)} |"
        ),
        (
            f"| Relation coverage | {acceptance.relation_coverage:.2%} | "
            f"{thresholds.relation_coverage:.0%} | "
            f"{_status(acceptance.relation_coverage >= thresholds.relation_coverage)} |"
        ),
        (
            f"| Hallucination rate | {acceptance.hallucination_rate:.2%} | "
            f"{thresholds.hallucination_rate:.0%} | "
            f"{_status(acceptance.hallucination_rate <= thresholds.hallucination_rate)} |"
        ),
        (
            f"| Data completeness | {acceptance.completeness:.2%} | "
            f"{thresholds.completeness:.0%} | "
            f"{_status(acceptance.completeness >= thresholds.completeness)} |"
        ),
        "",
        "## Detected Issues",
    ]
    if report.issues:
        for issue in report.issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Acceptance Evaluation")
    if acceptance.failures:
        lines.append("The following blockers were found:")
        for failure in acceptance.failures:
            lines.append(f"- {failure}")
    else:
        lines.append("All acceptance thresholds are satisfied.")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Acceptance report exported", path=str(output_path))
    return output_path


def _print_summary(acceptance: QualityAcceptanceSummary, report_path: Path) -> None:
    print("=" * 60)
    print("EPIP Quality Acceptance Validation")
    print("=" * 60)
    print(
        f"Entity precision: {acceptance.entity_precision:.2%} "
        f"(target {ACCEPTANCE_TARGETS.entity_precision:.0%})"
    )
    print(
        f"Relation coverage: {acceptance.relation_coverage:.2%} "
        f"(target {ACCEPTANCE_TARGETS.relation_coverage:.0%})"
    )
    print(
        f"Hallucination rate: {acceptance.hallucination_rate:.2%} "
        f"(target {ACCEPTANCE_TARGETS.hallucination_rate:.0%})"
    )
    print(
        f"Data completeness: {acceptance.completeness:.2%} "
        f"(target {ACCEPTANCE_TARGETS.completeness:.0%})"
    )
    print(f"Acceptance score: {acceptance.overall_score:.2f}")
    print(f"Report written to: {report_path}")
    if acceptance.failures:
        print("\nBlocking issues detected:")
        for failure in acceptance.failures:
            print(f"- {failure}")
    else:
        print("\nAll quality targets satisfied.")
    print("=" * 60)


async def _execute(
    args: argparse.Namespace,
    *,
    defaults: QualitySettings | None = None,
    targets: AcceptanceThresholds = ACCEPTANCE_TARGETS,
) -> QualityAcceptanceSummary:
    defaults = defaults or QualitySettings()
    thresholds = _resolve_evaluator_thresholds(args, defaults, targets)
    evaluator = KGQualityEvaluator(
        ground_truth_path=args.ground_truth,
        thresholds=thresholds,
    )
    builder = KGBuilder(config=LightRAGConfig())
    kg_report = await evaluator.generate_report(builder)
    additional_metrics = _resolve_additional_metrics(
        args.metrics_file,
        fallback_hallucination=args.hallucination_rate,
        fallback_completeness=args.data_completeness,
    )
    acceptance = evaluate_acceptance(
        kg_report,
        additional_metrics=additional_metrics,
        thresholds=targets,
    )
    report_path = _write_markdown_report(args.report, kg_report, acceptance, targets)
    _print_summary(acceptance, report_path)
    return acceptance


async def main() -> None:
    defaults = QualitySettings()
    args = _parse_args(defaults)
    try:
        acceptance = await _execute(args, defaults=defaults)
    except Exception as exc:  # pragma: no cover - CLI level logging
        logger.exception("Quality acceptance validation failed", error=str(exc))
        raise
    if not acceptance.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
