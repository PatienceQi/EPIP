"""Tests for the relation analysis CLI script."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import scripts.analyze_relations as analyze_relations
from epip.core.relation_extractor import GraphHealthReport, RelationReport, SubgraphInfo


@pytest.mark.asyncio
async def test_execute_generates_reports_and_validates(monkeypatch, tmp_path):
    args = SimpleNamespace(report=tmp_path / "report.md", auto_fix=True)
    fake_builder = MagicMock()
    monkeypatch.setattr(analyze_relations, "KGBuilder", lambda config: fake_builder)

    fake_report = RelationReport(
        total_relations=4,
        relation_type_counts={"SUPPORTED_BY": 4},
        low_confidence_count=1,
        average_confidence=0.82,
        sample_relations=[],
    )

    class DummyReportGenerator:
        def __init__(self, config):
            self.config = config
            self.generated_with = None

        async def generate_report(self, builder):
            self.generated_with = builder
            return fake_report

        def export_markdown(self, report, path):
            path.write_text("content", encoding="utf-8")
            return path

    report_generator = DummyReportGenerator(config=None)
    monkeypatch.setattr(
        analyze_relations,
        "RelationReportGenerator",
        lambda config: report_generator,
    )

    fake_health = GraphHealthReport(
        subgraph=SubgraphInfo(
            node_count=5,
            edge_count=4,
            is_connected=False,
            component_count=2,
        ),
        isolated_nodes=["NodeA"],
        bridge_suggestions=[("NodeA", "ASSOCIATED_WITH", "NodeB")],
    )

    class DummyValidator:
        def __init__(self, analyzer):
            self.analyzer = analyzer
            self.validate = AsyncMock(return_value=fake_health)
            self.fix_issues = AsyncMock(return_value=2)

    validator = DummyValidator(analyzer=None)
    monkeypatch.setattr(analyze_relations, "GraphValidator", lambda analyzer: validator)

    created_analyzers: list[object] = []

    class DummyAnalyzer:
        def __init__(self, config):
            self.config = config
            created_analyzers.append(self)

    monkeypatch.setattr(analyze_relations, "SubgraphAnalyzer", DummyAnalyzer)

    result_path = await analyze_relations._execute(args)

    assert result_path == args.report
    assert args.report.exists()
    assert report_generator.generated_with is fake_builder
    assert validator.validate.await_count == 1
    assert validator.validate.await_args_list[0].args[0] is fake_builder
    assert validator.fix_issues.await_count == 1
    assert validator.fix_issues.await_args_list[0].args[0] is fake_builder
    assert validator.fix_issues.await_args_list[0].kwargs["auto_fix"] is True
    assert len(created_analyzers) == 1
