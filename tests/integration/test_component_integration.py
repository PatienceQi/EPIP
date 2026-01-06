"""Component-level integration tests for EPIP subsystems."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pytest

from epip.api.visualization import VisualizationMemoryStore
from epip.config import CypherExecutorSettings, ReActSettings
from epip.core.llm_backend import LLMBackend
from epip.query.cypher import CypherGenerator
from epip.query.executor import CypherExecutor
from epip.query.linker import EntityLinker, LinkedEntity
from epip.query.parser import EntityMention, ParsedQuery, QueryConstraint, QueryIntent, QueryParser
from epip.query.planner import QueryPlanner
from epip.reasoning.react import ActionType, ReActAgent
from epip.verification.fact_extractor import ExtractedFact, FactType
from epip.verification.fact_verifier import (
    Evidence,
    FactVerifier,
    VerificationResult,
    VerificationStatus,
)
from epip.verification.path_analyzer import PathAnalyzer
from epip.verification.report import ReportGenerator
from epip.verification.trace import ReasoningTrace, TraceEdge, TraceNode, TraceRecorder
from epip.visualization import VisualizationDataGenerator

pytestmark = pytest.mark.asyncio


class SequencedLLM(LLMBackend):
    """Deterministic backend that replays provided payloads."""

    def __init__(self, payloads: list[str] | str) -> None:
        super().__init__()
        self._payloads = [payloads] if isinstance(payloads, str) else payloads
        self._index = 0

    async def generate(self, prompt: str, **_: object) -> str:
        if not self._payloads:
            return "{}"
        if self._index >= len(self._payloads):
            return self._payloads[-1]
        payload = self._payloads[self._index]
        self._index += 1
        return payload


class CatalogKG:
    """KG stub exposing entity catalog and simple query capability."""

    def __init__(self) -> None:
        self.catalog = [
            {"id": "kg:alpha", "name": "Policy Alpha", "entity_type": "POLICY"},
            {"id": "kg:beta", "name": "Policy Beta", "entity_type": "POLICY"},
        ]
        self.queries: list[tuple[str, str]] = []

    async def list_entities(self):
        return list(self.catalog)

    async def query(self, question: str, *, mode: str = "mix") -> str:
        normalized = question.strip()
        self.queries.append((normalized, mode))
        return f"{mode}:{normalized}"


class DummyNeo4jClient:
    """Lightweight Neo4j client stub used to test the executor."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def run_cypher(self, statement: str, parameters: dict | None = None) -> list[dict]:
        self.statements.append(statement)
        return [
            {
                "nodes": [{"id": parameters.get("n0_id", "n-0") if parameters else "n-0"}],
                "relationships": [],
                "path": {"statement": statement},
            }
        ]


class EvidenceKG:
    """KG stub that returns a single piece of evidence per fact."""

    async def find_fact_evidence(self, fact: ExtractedFact):
        return [
            {
                "source_type": "kg_node",
                "source_id": fact.fact_id,
                "content": f"{fact.subject} supports {fact.predicate}",
                "confidence": 0.85,
            }
        ]


@pytest.fixture(autouse=True)
def _patch_entity_linker_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed(self, texts):
        vectors = []
        for idx, text in enumerate(texts, start=1):
            vectors.append([float(len(text) + idx), float(idx)])
        return np.array(vectors, dtype=np.float32)

    monkeypatch.setattr(EntityLinker, "_embed_texts", fake_embed)


async def test_query_parser_with_linker() -> None:
    payload = json.dumps(
        {
            "intent": "relation",
            "entities": [
                {"text": "Policy Alpha", "type": "POLICY", "start": 0, "end": 12},
            ],
            "constraints": [],
            "complexity": 1,
        }
    )
    parser = QueryParser(backend=SequencedLLM(payload))
    linker = EntityLinker(similarity_threshold=0.3, max_alternatives=1)
    kg_builder = CatalogKG()

    parsed = await parser.parse("Policy Alpha relationships?")
    linked = await linker.link(parsed.entities, kg_builder)

    assert parsed.entities[0].text == "Policy Alpha"
    assert linked and linked[0].kg_node_id == "kg:alpha"
    assert linked[0].confidence > 0


async def test_cypher_generator_with_executor() -> None:
    mentions = [
        EntityMention(text="Policy Alpha", entity_type="POLICY", start=0, end=12),
        EntityMention(text="Policy Beta", entity_type="POLICY", start=17, end=28),
    ]
    parsed = ParsedQuery(
        original="Compare Alpha and Beta",
        intent=QueryIntent.RELATION,
        entities=mentions,
        constraints=[QueryConstraint(field="year", operator="=", value="2023")],
        complexity=2,
    )
    linked = [
        LinkedEntity(
            mention=mentions[0],
            kg_node_id="kg:alpha",
            kg_node_name="Policy Alpha",
            confidence=0.9,
        ),
        LinkedEntity(
            mention=mentions[1],
            kg_node_id="kg:beta",
            kg_node_name="Policy Beta",
            confidence=0.88,
        ),
    ]
    planner = QueryPlanner(id_factory=lambda: "plan-cypher")
    plan = await planner.plan(parsed, linked)
    generator = CypherGenerator(default_timeout=0.0, default_relation="SUPPORTED_BY")
    executor = CypherExecutor(
        DummyNeo4jClient(),
        settings=CypherExecutorSettings(timeout=0.0, max_retries=0),
    )

    query = generator.from_plan(plan)
    result = await executor.execute_with_fallback(query)

    assert "MATCH" in query.statement
    assert not result.timed_out
    assert result.nodes


async def test_react_agent_with_kg() -> None:
    backend = SequencedLLM(
        [
            json.dumps(
                {
                    "reasoning": "Search KG for Alpha signals.",
                    "action": "search",
                    "action_input": {"question": "Policy Alpha 2023", "confidence": 0.7},
                }
            ),
            json.dumps(
                {
                    "reasoning": "Aggregate what was found.",
                    "action": "aggregate",
                    "action_input": {},
                }
            ),
            json.dumps(
                {
                    "reasoning": "Conclude with best effort.",
                    "action": "conclude",
                    "action_input": {"confidence": 0.72},
                }
            ),
        ]
    )
    agent = ReActAgent(
        kg_builder=CatalogKG(),
        llm_backend=backend,
        settings=ReActSettings(max_iterations=4, timeout_per_step=1.0),
    )

    trace = await agent.reason("How did Policy Alpha perform in 2023?")

    assert trace.thoughts[0].action is ActionType.SEARCH
    assert trace.thoughts[-1].action is ActionType.CONCLUDE
    assert trace.final_answer
    assert trace.total_steps == 3


async def test_verification_with_trace() -> None:
    fact = ExtractedFact(
        fact_id="fact-trace",
        content="Policy Beta reduced cost.",
        fact_type=FactType.RELATION,
        subject="Policy Beta",
        predicate="reduced",
        object="cost",
        source_span=(0, 28),
    )
    verifier = FactVerifier(kg_client=EvidenceKG(), llm_backend=SequencedLLM("Looks valid."))
    result = await verifier.verify(fact)

    recorder = TraceRecorder()
    observation = recorder.record_node("observation", fact.content, result.confidence, ["kg:beta"])
    conclusion = recorder.record_node("conclusion", result.explanation, 0.6, [])
    recorder.record_edge(observation, conclusion, "supports", 0.3)
    trace = recorder.build_trace("Verify Policy Beta statement")

    analysis = PathAnalyzer().analyze(trace)

    assert result.status in {
        VerificationStatus.VERIFIED,
        VerificationStatus.PARTIALLY_VERIFIED,
    }
    assert trace.total_steps == 2
    assert analysis.path_length == trace.total_steps
    assert analysis.quality_score > 0


async def test_visualization_with_verification() -> None:
    fact = ExtractedFact(
        fact_id="fact-vis",
        content="Policy Alpha increased training.",
        fact_type=FactType.ATTRIBUTE,
        subject="Policy Alpha",
        predicate="increased",
        object="training",
        source_span=(0, 32),
    )
    evidence = Evidence(
        source_type="document",
        source_id="doc-1",
        content="Training directive 2023",
        confidence=0.8,
    )
    result = VerificationResult(
        fact=fact,
        status=VerificationStatus.VERIFIED,
        confidence=0.82,
        evidences=[evidence],
        conflicts=[],
        explanation="Confirmed by directive.",
    )
    report = ReportGenerator().generate([result], answer_id="answer-vis")
    generator = VisualizationDataGenerator()
    graph = generator.from_verification(report)
    store = VisualizationMemoryStore()
    store.set_report(report)

    now = datetime.now(UTC)
    trace = ReasoningTrace(
        trace_id="trace-vis",
        query="Explain visualization flow",
        nodes=[
            TraceNode(
                node_id="node-1",
                node_type="thought",
                content="Plan verification",
                confidence=0.7,
                timestamp=now,
            ),
            TraceNode(
                node_id="node-2",
                node_type="observation",
                content="Collected evidence",
                confidence=0.6,
                timestamp=now,
            ),
        ],
        edges=[TraceEdge(source_id="node-1", target_id="node-2", edge_type="supports", weight=0.5)],
        critical_path=["node-1", "node-2"],
        total_steps=2,
        avg_confidence=0.65,
    )
    store.set_trace(trace)
    answer_context = await store.get_node_context("answer:answer-vis")

    assert graph.nodes and graph.edges
    assert graph.nodes[0].metadata["total_facts"] == 1
    assert answer_context["metadata"]["verified"] == 1
