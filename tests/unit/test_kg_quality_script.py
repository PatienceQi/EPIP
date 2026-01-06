"""Tests for the KG quality evaluation CLI script."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import scripts.evaluate_kg_quality as kg_quality_script
from epip.core.kg_quality import (
    EntityQualityMetrics,
    GraphQualityMetrics,
    KGQualityReport,
    RelationQualityMetrics,
)


@pytest.mark.asyncio
async def test_execute_runs_full_flow(monkeypatch, tmp_path):
    args = SimpleNamespace(
        ground_truth=tmp_path / "expected.yaml",
        report=tmp_path / "kg_report.md",
        json=tmp_path / "kg_report.json",
        threshold_file=None,
    )

    defaults = kg_quality_script.QualitySettings()

    entity_metrics = EntityQualityMetrics(
        precision=0.9,
        recall=0.8,
        f1=0.85,
        missing_entities=[],
    )
    relation_metrics = RelationQualityMetrics(
        coverage=0.95,
        missing_relations=[],
    )
    graph_metrics = GraphQualityMetrics(
        node_count=10,
        edge_count=12,
        component_count=1,
        isolated_ratio=0.0,
        density=0.1,
        avg_degree=2.4,
    )
    fake_report = KGQualityReport(
        entity_metrics=entity_metrics,
        relation_metrics=relation_metrics,
        graph_metrics=graph_metrics,
        overall_score=92.0,
        passed=True,
        issues=[],
        score_breakdown={"Entities": 0.9, "Relations": 1.0, "Graph": 0.86},
    )

    class DummyEvaluator:
        def __init__(self, ground_truth_path, thresholds):
            self.ground_truth_path = ground_truth_path
            self.thresholds = thresholds
            self.generate_report = AsyncMock(return_value=fake_report)

        def export_markdown(self, report, output_path):
            output_path.write_text("markdown", encoding="utf-8")
            return output_path

        def export_json(self, report, output_path):
            output_path.write_text("{}", encoding="utf-8")
            return output_path

    dummy_evaluator = DummyEvaluator(args.ground_truth, defaults.as_thresholds())
    monkeypatch.setattr(
        kg_quality_script,
        "KGQualityEvaluator",
        lambda ground_truth_path, thresholds: dummy_evaluator,
    )

    class DummyBuilder:
        def __init__(self, config):
            self.config = config

    dummy_builder = DummyBuilder(config=None)
    monkeypatch.setattr(
        kg_quality_script,
        "KGBuilder",
        lambda config: dummy_builder,
    )

    generated_charts: list[str] = []

    class DummyGenerator:
        def generate_ascii_chart(self, scores, width=30):
            generated_charts.append(scores)
            return "chart"

    monkeypatch.setattr(
        kg_quality_script,
        "QualityReportGenerator",
        lambda: DummyGenerator(),
    )

    report = await kg_quality_script._execute(args, defaults)

    assert report is fake_report
    assert dummy_evaluator.generate_report.await_count == 1
    assert args.report.exists()
    assert args.json.exists()
    assert generated_charts == [fake_report.score_breakdown]


@pytest.mark.asyncio
async def test_main_exits_with_nonzero_on_failure(monkeypatch):
    args = SimpleNamespace(
        ground_truth=Path("dummy"),
        report=Path("dummy.md"),
        json=Path("dummy.json"),
        threshold_file=None,
    )

    monkeypatch.setattr(
        kg_quality_script,
        "_parse_args",
        lambda defaults: args,
    )

    async def fake_execute(*_, **__):
        class _Report:
            passed = False

        return _Report()

    monkeypatch.setattr(
        kg_quality_script,
        "_execute",
        fake_execute,
    )

    with pytest.raises(SystemExit) as excinfo:
        await kg_quality_script.main()
    assert excinfo.value.code == 1
