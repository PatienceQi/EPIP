"""Tests for the ReAct multi-step reasoning components."""

from __future__ import annotations

import json

import pytest

from epip.config import ReActSettings
from epip.core.llm_backend import LLMBackend
from epip.reasoning.aggregator import ResultAggregator
from epip.reasoning.decomposer import QueryDecomposer
from epip.reasoning.react import ActionType, ReActAgent, Thought


class StubBackend(LLMBackend):
    """LLM backend that returns pre-defined payloads."""

    def __init__(self, responses: list[str]) -> None:
        super().__init__()
        self._responses = responses
        self._calls = 0

    async def generate(self, prompt: str, **_: object) -> str:  # pragma: no cover - trivial
        if self._calls >= len(self._responses):
            return self._responses[-1]
        response = self._responses[self._calls]
        self._calls += 1
        return response


class DummyKG:
    """Stub knowledge-graph client for tests."""

    def __init__(self) -> None:
        self.invocations: list[tuple[str, str]] = []

    async def query(self, question: str, mode: str = "mix") -> str:
        self.invocations.append((question, mode))
        return f"{mode}:{question}"


@pytest.mark.asyncio
async def test_query_decomposer_generates_execution_plan():
    decomposer = QueryDecomposer()
    query = (
        "Analyze how vaccination rates influence hospital load, "
        "determine downstream impacts on 2023 budgets, and summarize risks."
    )

    result = await decomposer.decompose(query)

    assert result.original == query.strip()
    assert 3 <= len(result.sub_queries) <= 5
    plan_nodes = [node for layer in result.execution_order for node in layer]
    assert set(plan_nodes) == {sub.id for sub in result.sub_queries}
    for sub in result.sub_queries:
        assert set(sub.depends_on).issubset({sq.id for sq in result.sub_queries})


def test_result_aggregator_deduplicates_and_ranks():
    aggregator = ResultAggregator()
    raw_results = [
        {
            "content": "Hospital capacity improved",
            "confidence": 0.45,
            "path_length": 4,
            "source_queries": ["q1"],
        },
        {
            "content": "Hospital capacity improved ",
            "confidence": 0.4,
            "path_length": 3,
            "source_queries": ["q2"],
        },
        {
            "content": "Budget deficit widened",
            "confidence": 0.8,
            "path_length": 1,
            "source_queries": ["q3"],
        },
    ]

    ranked = aggregator.aggregate(raw_results, strategy="balanced")

    assert len(ranked) == 2
    assert ranked[0].content == "Budget deficit widened"
    assert ranked[0].confidence == pytest.approx(0.8)
    assert set(ranked[1].source_queries) == {"q1", "q2"}


@pytest.mark.asyncio
async def test_react_agent_reason_runs_until_conclusion():
    backend = StubBackend(
        [
            json.dumps(
                {
                    "reasoning": "Need evidence on vaccination impact.",
                    "action": "search",
                    "action_input": {"question": "vaccination impact", "confidence": 0.7},
                }
            ),
            json.dumps(
                {
                    "reasoning": "Summarize findings collected so far.",
                    "action": "aggregate",
                    "action_input": {},
                }
            ),
            json.dumps(
                {
                    "reasoning": "Use aggregated data to answer the query.",
                    "action": "conclude",
                    "action_input": {"confidence": 0.85},
                }
            ),
        ]
    )
    kg = DummyKG()
    agent = ReActAgent(
        kg_builder=kg,
        llm_backend=backend,
        settings=ReActSettings(max_iterations=5, timeout_per_step=1.0),
    )

    trace = await agent.reason("How do vaccination policies influence hospital admissions?")

    assert trace.total_steps == 3
    assert trace.thoughts[-1].action is ActionType.CONCLUDE
    assert trace.final_answer
    assert 0 < trace.confidence <= 1
    assert any("vaccination impact" in question for question, _ in kg.invocations)


def test_react_agent_termination_logic():
    backend = StubBackend(
        [
            json.dumps(
                {
                    "reasoning": "Start with search.",
                    "action": "search",
                    "action_input": {"question": "q"},
                }
            )
        ]
    )
    kg = DummyKG()
    agent = ReActAgent(
        kg_builder=kg,
        llm_backend=backend,
        settings=ReActSettings(max_iterations=2, timeout_per_step=1.0),
    )
    search_thought = Thought(step=1, reasoning="search", action=ActionType.SEARCH, action_input={})
    assert not agent._should_terminate(search_thought, 1)
    assert agent._should_terminate(search_thought, 2)
    conclude_thought = Thought(
        step=2,
        reasoning="done",
        action=ActionType.CONCLUDE,
        action_input={},
    )
    assert agent._should_terminate(conclude_thought, 1)
