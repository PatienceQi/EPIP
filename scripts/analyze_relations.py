"""Analyze relations and connectivity within LightRAG knowledge graphs."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import structlog

from epip.config import LightRAGConfig, get_relation_extraction_config
from epip.core.kg_builder import KGBuilder
from epip.core.relation_extractor import (
    GraphValidator,
    RelationReportGenerator,
    SubgraphAnalyzer,
)

logger = structlog.get_logger()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect LightRAG relations and connectivity")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/reports/relation_report.md"),
        help="Path to export the Markdown report",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Automatically link components using suggested bridge relations",
    )
    return parser.parse_args()


async def _execute(args: argparse.Namespace) -> Path:
    relation_config = get_relation_extraction_config()
    builder = KGBuilder(config=LightRAGConfig())
    analyzer = SubgraphAnalyzer(config=relation_config)
    report_generator = RelationReportGenerator(config=relation_config)
    validator = GraphValidator(analyzer=analyzer)

    print("=" * 60)
    print("EPIP Relation Analysis")
    print("=" * 60)

    report = await report_generator.generate_report(builder)
    report_path = report_generator.export_markdown(report, args.report)

    print("[Relations]")
    print(f"Total relations: {report.total_relations}")
    print(
        f"Low confidence relations (<{relation_config.confidence_threshold}): "
        f"{report.low_confidence_count}"
    )
    print(f"Average confidence: {report.average_confidence:.2f}")
    print(f"Markdown exported to: {report_path}")

    health = await validator.validate(builder)
    subgraph = health.subgraph

    print("\n[Connectivity]")
    print(f"Nodes: {subgraph.node_count}, Edges: {subgraph.edge_count}")
    print(f"Connected: {subgraph.is_connected}, Components: {subgraph.component_count}")

    if health.isolated_nodes:
        preview = ", ".join(health.isolated_nodes[:10])
        print(
            f"Isolated nodes ({len(health.isolated_nodes)} total): "
            f"{preview}{' ...' if len(health.isolated_nodes) > 10 else ''}"
        )
    else:
        print("No isolated nodes detected.")

    if health.bridge_suggestions:
        print("Bridge suggestions:")
        for source, relation_type, target in health.bridge_suggestions:
            print(f"  - {source} --{relation_type}--> {target}")
    else:
        print("Graph is already connected.")

    if args.auto_fix:
        fixes = await validator.fix_issues(builder, auto_fix=True)
        print(f"\n[Auto-fix] Applied {fixes} suggested bridge(s).")
        if fixes == 0:
            print("No bridges were applied; graph already connected or nodes missing.")

    print("=" * 60)
    return report_path


async def main() -> None:
    args = _parse_args()
    try:
        await _execute(args)
    except Exception as exc:  # pragma: no cover - CLI level logging
        logger.exception("Relation analysis failed", error=str(exc))
        raise


if __name__ == "__main__":
    asyncio.run(main())
