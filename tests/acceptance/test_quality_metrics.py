"""Acceptance tests for KG quality non-functional requirements."""

from __future__ import annotations

import pytest

from epip.core.kg_quality import (
    EntityQualityMetrics,
    GraphQualityMetrics,
    KGQualityReport,
    RelationQualityMetrics,
)
from scripts import validate_quality


def _build_report(
    *,
    entity_precision: float = 0.92,
    relation_coverage: float = 0.85,
) -> KGQualityReport:
    entity_metrics = EntityQualityMetrics(
        precision=entity_precision,
        recall=0.9,
        f1=0.91,
        missing_entities=[],
    )
    relation_metrics = RelationQualityMetrics(
        coverage=relation_coverage,
        missing_relations=[],
    )
    graph_metrics = GraphQualityMetrics(
        node_count=10,
        edge_count=15,
        component_count=1,
        isolated_ratio=0.02,
        density=0.03,
        avg_degree=3.0,
    )
    return KGQualityReport(
        entity_metrics=entity_metrics,
        relation_metrics=relation_metrics,
        graph_metrics=graph_metrics,
        overall_score=94.0,
        passed=True,
        issues=[],
        score_breakdown={"Entities": 0.94, "Relations": 0.88, "Graph": 0.9},
    )


def _extra_metrics(
    *,
    hallucination_rate: float = 0.03,
    completeness: float = 0.97,
) -> validate_quality.AdditionalQualityMetrics:
    return validate_quality.AdditionalQualityMetrics(
        hallucination_rate=hallucination_rate,
        completeness=completeness,
    )


def _evaluate(
    *,
    entity_precision: float = 0.92,
    relation_coverage: float = 0.85,
    hallucination_rate: float = 0.03,
    completeness: float = 0.97,
) -> validate_quality.QualityAcceptanceSummary:
    report = _build_report(
        entity_precision=entity_precision,
        relation_coverage=relation_coverage,
    )
    additional = _extra_metrics(
        hallucination_rate=hallucination_rate,
        completeness=completeness,
    )
    return validate_quality.evaluate_acceptance(report, additional_metrics=additional)


def test_entity_precision_meets_threshold():
    result = _evaluate(entity_precision=0.94)
    assert result.entity_precision >= validate_quality.ACCEPTANCE_TARGETS.entity_precision
    assert result.passed


def test_relation_coverage_meets_threshold():
    result = _evaluate(relation_coverage=0.84)
    assert result.relation_coverage >= validate_quality.ACCEPTANCE_TARGETS.relation_coverage
    assert result.passed


def test_hallucination_rate_below_threshold():
    result = _evaluate(hallucination_rate=0.045)
    assert result.hallucination_rate < validate_quality.ACCEPTANCE_TARGETS.hallucination_rate
    assert result.passed


def test_data_completeness_meets_threshold():
    result = _evaluate(completeness=0.96)
    assert result.completeness >= validate_quality.ACCEPTANCE_TARGETS.completeness
    assert result.passed


def test_overall_quality_score():
    result = _evaluate(
        entity_precision=0.85,
        relation_coverage=0.78,
        hallucination_rate=0.06,
        completeness=0.91,
    )
    assert result.overall_score == pytest.approx(92.77, rel=1e-3)
    assert result.passed is False
    assert any("Entity precision" in failure for failure in result.failures)
    assert any("Relation coverage" in failure for failure in result.failures)
    assert any("Hallucination rate" in failure for failure in result.failures)
    assert any("Data completeness" in failure for failure in result.failures)
