"""Tests for entity extraction utilities."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from epip.core.entity_extractor import (
    EntityDisambiguator,
    EntityEvaluator,
    EntityExtractionConfig,
    EntityReportGenerator,
)
from epip.core.kg_builder import KGStats


def test_entity_extraction_config_defaults():
    config = EntityExtractionConfig()

    assert config.confidence_threshold == 0.6
    assert config.max_entities_per_chunk == 50
    assert config.enable_disambiguation is True
    assert config.similarity_threshold == pytest.approx(0.85)
    assert "POLICY" in config.entity_types
    assert config.report_sample_size == 20


@pytest.mark.asyncio
async def test_find_similar_entities_filters_candidates(monkeypatch):
    disambiguator = EntityDisambiguator(similarity_threshold=0.9)

    async def fake_embed(self, texts):
        assert len(texts) == 3
        return np.array(
            [
                [1.0, 0.0],  # query
                [0.9, 0.0],  # aligned
                [0.0, 1.0],  # orthogonal
            ],
            dtype=float,
        )

    monkeypatch.setattr(EntityDisambiguator, "_embed_texts", fake_embed)

    result = await disambiguator.find_similar_entities(
        "Health Bureau",
        ["Health Bureau", "Financial Secretary"],
    )

    assert len(result) == 1
    assert result[0][0] == "Health Bureau"
    assert result[0][1] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_entity_report_generator_compiles_statistics(monkeypatch):
    config = EntityExtractionConfig(report_sample_size=2)
    generator = EntityReportGenerator(config=config)
    builder = MagicMock()
    stats = KGStats(
        total_entities=12,
        total_relations=5,
        entity_types={"POLICY": 8},
        relation_types={},
    )
    builder.get_statistics = AsyncMock(return_value=stats)

    async def fake_collect(self, builder_arg, limit):
        assert builder_arg is builder
        assert limit == config.report_sample_size
        return (
            [
                {
                    "name": "Policy Alpha",
                    "type": "POLICY",
                    "confidence": 0.92,
                    "aliases": ["Alpha Policy"],
                }
            ],
            3,
            1,
        )

    monkeypatch.setattr(EntityReportGenerator, "_collect_entity_samples", fake_collect)

    report = await generator.generate_report(builder)

    assert report.total_entities == stats.total_entities
    assert report.entity_type_counts == stats.entity_types
    assert report.low_confidence_count == 3
    assert report.disambiguation_count == 1
    assert report.sample_entities[0]["name"] == "Policy Alpha"


def test_entity_evaluator_computes_metrics(tmp_path: Path):
    ground_truth = [
        {"name": "政策A", "type": "POLICY"},
        {"name": "Hospital Authority", "type": "ORGANIZATION"},
    ]
    ground_truth_path = tmp_path / "ground_truth.json"
    ground_truth_path.write_text(json.dumps(ground_truth), encoding="utf-8")

    evaluator = EntityEvaluator(ground_truth_path)
    extracted = [
        {"name": "政策A", "type": "POLICY"},
        {"name": "未知指标", "type": "METRIC"},
    ]

    result = evaluator.evaluate(extracted)

    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(0.5)
    assert result.f1_score == pytest.approx(0.5)
    assert result.confusion_matrix["POLICY"]["POLICY"] == 1
    assert result.confusion_matrix["UNKNOWN"]["METRIC"] == 1
