"""Tests for KG quality evaluation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import epip.core.kg_quality as kg_quality
from epip.core.kg_quality import (
    KGQualityEvaluator,
    QualityReportGenerator,
    QualityThresholds,
)


def _write_ground_truth(path: Path) -> None:
    path.write_text(
        """
        entities:
          - name: "Policy A"
          - name: "Policy B"
          - name: "Policy C"
        relations:
          - source: "Policy A"
            relation_type: "SUPPORTED_BY"
            target: "Policy B"
          - source: "Policy B"
            relation_type: "COORDINATES_WITH"
            target: "Policy C"
        """,
        encoding="utf-8",
    )


def _sample_snapshot() -> kg_quality._GraphSnapshot:
    return kg_quality._GraphSnapshot(
        nodes={
            "1": {"name": "Policy A"},
            "2": {"name": "Policy B"},
            "3": {"name": "External Partner"},
        },
        edges=[
            ("1", "2", {"relation_type": "SUPPORTED_BY", "confidence": 0.9}),
            ("3", "2", {"relation_type": "LOCATED_IN", "confidence": 0.5}),
        ],
    )


@pytest.mark.asyncio
async def test_evaluator_computes_metrics(monkeypatch, tmp_path):
    ground_truth = tmp_path / "expected.yaml"
    _write_ground_truth(ground_truth)

    evaluator = KGQualityEvaluator(ground_truth_path=ground_truth)
    snapshot = _sample_snapshot()
    monkeypatch.setattr(
        kg_quality,
        "_get_graph_snapshot",
        AsyncMock(return_value=snapshot),
    )

    builder = MagicMock()
    entity_metrics = await evaluator.evaluate_entities(builder)
    relation_metrics = await evaluator.evaluate_relations(builder)
    graph_metrics = await evaluator.evaluate_graph(builder)

    assert pytest.approx(entity_metrics.precision, rel=1e-6) == pytest.approx(2 / 3, rel=1e-6)
    assert pytest.approx(entity_metrics.recall, rel=1e-6) == pytest.approx(2 / 3, rel=1e-6)
    assert entity_metrics.missing_entities == ["Policy C"]

    assert relation_metrics.coverage == pytest.approx(0.5)
    assert relation_metrics.missing_relations == ["Policy B --COORDINATES_WITH--> Policy C"]

    assert graph_metrics.node_count == 3
    assert graph_metrics.edge_count == 2
    assert graph_metrics.component_count == 1
    assert graph_metrics.isolated_ratio == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_generate_report_exports_and_detects_issues(monkeypatch, tmp_path):
    ground_truth = tmp_path / "expected.yaml"
    _write_ground_truth(ground_truth)

    thresholds = QualityThresholds(
        entity_precision=0.95,
        entity_recall=0.95,
        relation_coverage=0.9,
        graph_density=0.5,
        min_avg_degree=3.0,
        max_isolated_ratio=0.0,
    )
    evaluator = KGQualityEvaluator(
        ground_truth_path=ground_truth,
        thresholds=thresholds,
    )

    tiny_snapshot = kg_quality._GraphSnapshot(
        nodes={"1": {"name": "Single Node"}},
        edges=[],
    )
    monkeypatch.setattr(
        kg_quality,
        "_get_graph_snapshot",
        AsyncMock(return_value=tiny_snapshot),
    )

    report = await evaluator.generate_report(MagicMock())
    assert report.passed is False
    assert report.overall_score < 100
    assert report.issues  # at least one issue raised

    markdown_path = evaluator.export_markdown(report, tmp_path / "kg_report.md")
    json_path = evaluator.export_json(report, tmp_path / "kg_report.json")

    markdown_content = markdown_path.read_text(encoding="utf-8")
    assert "Knowledge Graph Quality Report" in markdown_content
    assert "Issues" in markdown_content

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["overall_score"] == pytest.approx(report.overall_score)
    assert payload["issues"] == report.issues


def test_ascii_chart_generation():
    generator = QualityReportGenerator()
    chart = generator.generate_ascii_chart({"Entities": 0.5, "Graph": 0.8}, width=10)
    assert "Entities" in chart
    assert "[#####-----]" in chart
    assert "80.0%" in chart
