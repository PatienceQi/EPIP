"""Tests for the query parsing, linking, and planning components."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from epip.core.llm_backend import LLMBackend
from epip.query.linker import EntityLinker, LinkedEntity
from epip.query.parser import EntityMention, ParsedQuery, QueryConstraint, QueryIntent, QueryParser
from epip.query.planner import QueryPlanner


class DummyBackend(LLMBackend):
    """Lightweight backend used to stub LLM responses."""

    def __init__(self, payload: str, *, should_fail: bool = False) -> None:
        super().__init__()
        self.payload = payload
        self.should_fail = should_fail

    async def generate(self, prompt: str, **_: object) -> str:
        if self.should_fail:
            raise RuntimeError("LLM unavailable")
        return self.payload


@pytest.mark.asyncio
async def test_query_parser_parses_llm_payload():
    payload = """
    {
        "intent": "aggregate",
        "entities": [
            {"text": "Hospital Authority", "type": "ORGANIZATION", "start": 6, "end": 24}
        ],
        "constraints": [{"field": "time", "operator": "=", "value": "2023"}],
        "complexity": 3
    }
    """
    parser = QueryParser(backend=DummyBackend(payload))

    parsed = await parser.parse("How many Hospital Authority visits in 2023?")

    assert parsed.intent is QueryIntent.AGGREGATE
    assert parsed.entities[0].text == "Hospital Authority"
    assert parsed.constraints[0].field == "time"
    assert parsed.complexity == 3


@pytest.mark.asyncio
async def test_query_parser_falls_back_to_heuristics_for_chinese():
    parser = QueryParser(backend=DummyBackend("{}", should_fail=True))

    parsed = await parser.parse("香港2023年政策执行情况？")

    assert parsed.intent is QueryIntent.FACT
    assert any(mention.text == "香港" for mention in parsed.entities)
    assert parsed.constraints, "Should infer temporal constraints from the query."


@pytest.mark.asyncio
async def test_entity_linker_uses_catalog_and_similarity(monkeypatch):
    linker = EntityLinker(similarity_threshold=0.5, max_alternatives=2)
    mention = EntityMention(text="Health Bureau", entity_type="ORGANIZATION", start=0, end=12)

    async def fake_catalog(self, builder):
        assert builder is not None
        return [
            {"id": "1", "name": "Health Bureau", "entity_type": "ORGANIZATION"},
            {"id": "2", "name": "Hospital Authority", "entity_type": "ORGANIZATION"},
        ]

    async def fake_fuzzy(self, text, candidates, threshold):
        assert text == "Health Bureau"
        assert candidates == ["Health Bureau", "Hospital Authority"]
        assert threshold == linker.similarity_threshold
        return [("Health Bureau", 0.92), ("Hospital Authority", 0.6)]

    monkeypatch.setattr(EntityLinker, "_load_entity_catalog", fake_catalog)
    monkeypatch.setattr(EntityLinker, "fuzzy_match", fake_fuzzy)

    result = await linker.link([mention], kg_builder=MagicMock())

    assert len(result) == 1
    linked = result[0]
    assert linked.kg_node_id == "1"
    assert linked.alternatives == [("Hospital Authority", 0.6)]


@pytest.mark.asyncio
async def test_fuzzy_match_uses_embedding_similarity(monkeypatch):
    linker = EntityLinker()

    async def fake_embed(self, texts):
        assert len(texts) == 3
        return np.array(
            [
                [1.0, 0.0],  # base
                [0.9, 0.0],  # aligned
                [0.0, 1.0],  # orthogonal
            ]
        )

    monkeypatch.setattr(EntityLinker, "_embed_texts", fake_embed)

    matches = await linker.fuzzy_match(
        "Health Bureau",
        ["Health Bureau", "Budget Office"],
        threshold=0.5,
    )

    assert matches == [("Health Bureau", pytest.approx(1.0))]


@pytest.mark.asyncio
async def test_query_planner_generates_structured_plan():
    parsed = ParsedQuery(
        original="Compare admissions between 2022 and 2023",
        intent=QueryIntent.COMPARE,
        entities=[EntityMention("Hospital Authority", "ORGANIZATION", 8, 26)],
        constraints=[QueryConstraint(field="time", operator="between", value=["2022", "2023"])],
        complexity=3,
    )
    linked = [
        LinkedEntity(
            mention=parsed.entities[0],
            kg_node_id="n-1",
            kg_node_name="Hospital Authority",
            confidence=0.87,
            alternatives=[],
        )
    ]
    planner = QueryPlanner(id_factory=lambda: "plan-1")

    plan = await planner.plan(parsed, linked)

    assert plan.query_id == "plan-1"
    assert any(step.action == "aggregate" for step in plan.steps)
    assert not planner.validate_plan(plan)
    plan_json = planner.to_json(plan)
    assert '"query_id": "plan-1"' in plan_json
