"""Tests for relation analysis and graph validation utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from epip.core.kg_builder import KGBuilder, KGStats
from epip.core.relation_extractor import (
    GraphValidator,
    RelationExtractionConfig,
    RelationReportGenerator,
    SubgraphAnalyzer,
)


class DummyGraph:
    """Minimal graph stub mimicking networkx access patterns."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, object]] = {}
        self._edges: list[tuple[str, str, dict[str, object]]] = []

    def add_node(self, node_id: str, **attrs: object) -> None:
        self._nodes[str(node_id)] = dict(attrs)

    def add_edge(self, source: str, target: str, **attrs: object) -> None:
        self._edges.append((str(source), str(target), dict(attrs)))

    def nodes(self, data: bool = False):
        if data:
            return list(self._nodes.items())
        return list(self._nodes.keys())

    def edges(self, data: bool = False):
        if data:
            return list(self._edges)
        return [(source, target) for source, target, _ in self._edges]


class DummyStorage:
    def __init__(self, graph: DummyGraph) -> None:
        self._graph = graph

    async def _get_graph(self) -> DummyGraph:
        return self._graph


def _build_builder(graph: DummyGraph, stats: KGStats | None = None) -> KGBuilder:
    storage = DummyStorage(graph)
    rag = MagicMock()
    rag.chunk_entity_relation_graph = storage
    builder = MagicMock(spec=KGBuilder)
    builder._require_rag = MagicMock(return_value=rag)
    builder._ensure_initialized = AsyncMock()
    builder.get_statistics = AsyncMock(
        return_value=stats
        or KGStats(
            total_entities=0,
            total_relations=0,
            entity_types={},
            relation_types={},
        )
    )
    return builder


@pytest.mark.asyncio
async def test_subgraph_analyzer_detects_isolates_and_bridges():
    graph = DummyGraph()
    graph.add_node("1", name="Policy Alpha")
    graph.add_node("2", name="Policy Beta")
    graph.add_node("3", name="Policy Gamma")
    graph.add_edge("1", "2", relation_type="SUPPORTED_BY", confidence=0.91)

    builder = _build_builder(graph)
    config = RelationExtractionConfig(default_relation_type="COORDINATES_WITH")
    analyzer = SubgraphAnalyzer(config=config)

    info = await analyzer.analyze_connectivity(builder)
    assert info.node_count == 3
    assert info.edge_count == 1
    assert info.component_count == 2
    assert info.is_connected is False

    isolates = await analyzer.find_isolated_nodes(builder)
    assert isolates == ["Policy Gamma"]

    bridges = await analyzer.suggest_bridges(builder, max_suggestions=3)
    assert len(bridges) == 1
    assert bridges[0][2] == "Policy Gamma"
    assert bridges[0][1] == config.default_relation_type
    assert bridges[0][0] in {"Policy Alpha", "Policy Beta"}


@pytest.mark.asyncio
async def test_relation_report_generator_collects_samples(tmp_path: Path):
    graph = DummyGraph()
    graph.add_node("1", name="Agency A")
    graph.add_node("2", name="Agency B")
    graph.add_node("3", name="Agency C")
    graph.add_edge("1", "2", relation_type="SUPPORTED_BY", confidence=0.95)
    graph.add_edge("2", "3", relation_type="FUNDED_BY", confidence=0.45)

    stats = KGStats(
        total_entities=3,
        total_relations=2,
        entity_types={"AGENCY": 3},
        relation_types={"SUPPORTED_BY": 1, "FUNDED_BY": 1},
    )
    builder = _build_builder(graph, stats=stats)

    config = RelationExtractionConfig(confidence_threshold=0.6, report_sample_size=2)
    generator = RelationReportGenerator(config=config)

    report = await generator.generate_report(builder)
    assert report.total_relations == 2
    assert report.low_confidence_count == 1
    assert report.relation_type_counts["SUPPORTED_BY"] == 1
    assert report.sample_relations[0]["source"] == "Agency A"
    assert report.sample_relations[0]["relation_type"] == "SUPPORTED_BY"

    output = generator.export_markdown(report, tmp_path / "relation_report.md")
    assert output.exists()


@pytest.mark.asyncio
async def test_graph_validator_fix_issues_bridges_components():
    graph = DummyGraph()
    graph.add_node("1", name="Dept One")
    graph.add_node("2", name="Dept Two")
    graph.add_node("3", name="Dept Three")
    graph.add_edge("1", "2", relation_type="COOPERATES_WITH", confidence=0.8)

    builder = _build_builder(graph)
    analyzer = SubgraphAnalyzer(RelationExtractionConfig(default_relation_type="LINKED_WITH"))
    validator = GraphValidator(analyzer=analyzer)

    fixed = await validator.fix_issues(builder, auto_fix=True)

    assert fixed == 1
    edges = graph.edges(data=True)
    assert any(
        data["relation_type"] == "LINKED_WITH" and {source, target} in ({"1", "3"}, {"2", "3"})
        for source, target, data in edges
    )
