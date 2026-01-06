"""Generate entity reports and optional evaluation metrics."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import structlog

from epip.config import LightRAGConfig, get_entity_extraction_config
from epip.core.entity_extractor import EntityEvaluator, EntityReportGenerator
from epip.core.kg_builder import KGBuilder

logger = structlog.get_logger()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate entity extraction accuracy")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("data/ground_truth/sample_entities.json"),
        help="Path to labeled entity JSON file",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/reports/entity_report.md"),
        help="Path to export the Markdown report",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()

    print("=" * 60)
    print("EPIP Entity Evaluation")
    print("=" * 60)

    kg_config = LightRAGConfig()
    entity_config = get_entity_extraction_config()
    builder = KGBuilder(config=kg_config)
    report_generator = EntityReportGenerator(config=entity_config)

    report = await report_generator.generate_report(builder)
    report_path = report_generator.export_markdown(report, args.report)

    print("[Report]")
    print(f"Total entities: {report.total_entities}")
    print(f"Low confidence entities: {report.low_confidence_count}")
    print(f"Entities with aliases: {report.disambiguation_count}")
    print(f"Markdown exported to: {report_path}")

    ground_truth_path = args.ground_truth
    if ground_truth_path.exists():
        evaluator = EntityEvaluator(ground_truth_path)
        evaluation = evaluator.evaluate(report.sample_entities)
        print("\n[Evaluation]")
        print(f"Sample size: {len(report.sample_entities)}")
        print(f"Precision: {evaluation.precision:.2%}")
        print(f"Recall: {evaluation.recall:.2%}")
        print(f"F1 Score: {evaluation.f1_score:.2%}")
        print("Confusion matrix:")
        for actual, predictions in evaluation.confusion_matrix.items():
            entries = ", ".join(f"{pred}:{count}" for pred, count in predictions.items())
            print(f"  {actual} -> {entries}")
    else:
        logger.warning(
            "Ground truth file missing; skipping evaluation", path=str(ground_truth_path)
        )

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
