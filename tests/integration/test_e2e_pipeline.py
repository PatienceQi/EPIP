"""End-to-end integration tests for the EPIP pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from epip.api.visualization import VisualizationMemoryStore
from epip.config import CypherExecutorSettings, ReActSettings
from epip.core.data_processor import DataProcessor
from epip.core.hallucination import HallucinationGuard
from epip.core.kg_builder import InsertResult, KGStats
from epip.core.llm_backend import LLMBackend
from epip.core.query_engine import QueryEngine
from epip.query.cypher import CypherGenerator
from epip.query.executor import CypherExecutor
from epip.query.linker import EntityLinker
from epip.query.parser import QueryIntent, QueryParser
from epip.query.planner import QueryPlanner
from epip.reasoning.react import ActionType, ReActAgent
from epip.verification.fact_extractor import ExtractedFact, FactType
from epip.verification.fact_verifier import FactVerifier
from epip.verification.report import ReportGenerator
from epip.verification.trace import TraceRecorder
from epip.visualization import VisualizationDataGenerator

pytestmark = pytest.mark.asyncio


class SequencedLLM(LLMBackend):
    """LLM backend that replays predefined payloads."""

    def __init__(self, payloads: list[str] | str) -> None:
        super().__init__()
        if isinstance(payloads, str):
            self._payloads = [payloads]
        else:
            self._payloads = payloads
        self._cursor = 0

    async def generate(self, prompt: str, **_: object) -> str:
        if not self._payloads:
            return "{}"
        if self._cursor >= len(self._payloads):
            return self._payloads[-1]
        payload = self._payloads[self._cursor]
        self._cursor += 1
        return payload


class DummyNeo4jClient:
    """Synchronous stand-in for the Neo4j client used by CypherExecutor."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, dict]] = []

    def run_cypher(self, statement: str, parameters: dict | None = None) -> list[dict]:
        payload = parameters or {}
        self.statements.append((statement, payload))
        return [
            {
                "nodes": [{"id": payload.get("start", "n-0")}],
                "relationships": [{"type": "RELATES"}],
                "path": statement,
            }
        ]


class DummyKGBuilder:
    """Minimal KG builder that records interactions."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, str]] = []
        self.inserted_batches: list[list[Path]] = []
        self.catalog = [
            {"id": "kg:alpha", "name": "Policy Alpha", "entity_type": "POLICY"},
            {"id": "kg:beta", "name": "Policy Beta", "entity_type": "POLICY"},
        ]
        self._stats = KGStats(
            total_entities=42,
            total_relations=17,
            entity_types={"POLICY": 20, "ORG": 22},
            relation_types={"RELATED_TO": 17},
        )

    async def query(self, question: str, *, mode: str = "mix") -> str:
        normalized = question.strip()
        self.queries.append((normalized, mode))
        return f"{mode}:{normalized}"

    async def insert_documents(self, files: list[Path]) -> InsertResult:
        batch = [Path(path) for path in files]
        self.inserted_batches.append(batch)
        total_tokens = sum(path.stat().st_size for path in batch)
        return InsertResult(
            file_count=len(batch),
            entity_count=len(batch) * 5,
            relation_count=max(1, len(batch) * 2),
            errors=[] if total_tokens else ["empty batch"],
        )

    async def get_statistics(self) -> KGStats:
        return self._stats

    async def list_entities(self):
        return list(self.catalog)


class EvidenceKG:
    """Simple KG client that provides deterministic evidence."""

    async def find_fact_evidence(self, fact: ExtractedFact):
        return [
            {
                "source_type": "document",
                "source_id": f"doc-{fact.fact_id}",
                "content": f"{fact.subject} evidence for {fact.predicate}",
                "confidence": 0.9,
            }
        ]


@pytest.fixture(autouse=True)
def _patch_entity_linker_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed(self, texts):
        vectors = []
        for index, text in enumerate(texts, start=1):
            vectors.append([float(len(text) + index), float(index)])
        return np.array(vectors, dtype=np.float32)

    monkeypatch.setattr(EntityLinker, "_embed_texts", fake_embed)


async def test_data_import_to_kg_flow(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    csv_path = dataset_dir / "policies.csv"
    csv_path.write_text("policy,year\nAlpha,2023\nBeta,2024\n", encoding="utf-8")

    data_processor = DataProcessor(dataset_path=dataset_dir)
    discovered_files = data_processor.scan_dataset(dataset_dir)
    assert discovered_files, "DataProcessor should detect the synthetic dataset."

    kg_builder = DummyKGBuilder()
    engine = QueryEngine(
        data_processor=data_processor,
        kg_builder=kg_builder,
        hallucination_guard=HallucinationGuard(),
    )

    result = await engine.insert_documents([info.path for info in discovered_files])
    stats = await engine.statistics()

    assert result.file_count == len(discovered_files)
    assert kg_builder.inserted_batches[0][0] == csv_path
    assert stats.total_entities == 42
    assert stats.relation_types["RELATED_TO"] == 17


async def test_query_processing_flow() -> None:
    payload = json.dumps(
        {
            "intent": "aggregate",
            "entities": [
                {"text": "Policy Alpha", "type": "POLICY", "start": 0, "end": 12},
            ],
            "constraints": [{"field": "year", "operator": "between", "value": ["2022", "2023"]}],
            "complexity": 2,
        }
    )
    parser = QueryParser(backend=SequencedLLM(payload))
    linker = EntityLinker(similarity_threshold=0.3, max_alternatives=1)
    planner = QueryPlanner(id_factory=lambda: "plan-42")
    kg_builder = DummyKGBuilder()
    engine = QueryEngine(
        data_processor=DataProcessor(),
        kg_builder=kg_builder,
        hallucination_guard=HallucinationGuard(),
    )

    query = " Summarize Policy Alpha performance between 2022 and 2023. "
    parsed = await parser.parse(query)
    linked = await linker.link(parsed.entities, kg_builder)
    plan = await planner.plan(parsed, linked)
    response = await engine.query(query)

    assert parsed.intent is QueryIntent.AGGREGATE
    assert linked[0].kg_node_id == "kg:alpha"
    assert plan.steps and plan.query_id == "plan-42"
    assert response.startswith("mix:Summarize Policy Alpha performance")
    assert kg_builder.queries[-1][1] == "mix"


async def test_react_reasoning_flow() -> None:
    backend = SequencedLLM(
        [
            json.dumps(
                {
                    "reasoning": "Search for current readiness data.",
                    "action": "search",
                    "action_input": {"question": "readiness status", "confidence": 0.8},
                }
            ),
            json.dumps(
                {
                    "reasoning": "Traverse related policies for deeper evidence.",
                    "action": "traverse",
                    "action_input": {"question": "related policies", "mode": "path"},
                }
            ),
            json.dumps(
                {
                    "reasoning": "Aggregate intermediate observations.",
                    "action": "aggregate",
                    "action_input": {},
                }
            ),
            json.dumps(
                {
                    "reasoning": "Conclude using aggregated context.",
                    "action": "conclude",
                    "action_input": {"confidence": 0.88},
                }
            ),
        ]
    )
    agent = ReActAgent(
        kg_builder=DummyKGBuilder(),
        llm_backend=backend,
        settings=ReActSettings(max_iterations=6, timeout_per_step=1.0),
    )

    trace = await agent.reason("Explain hospital readiness for 2024 budgets.")

    assert [thought.action for thought in trace.thoughts] == [
        ActionType.SEARCH,
        ActionType.TRAVERSE,
        ActionType.AGGREGATE,
        ActionType.CONCLUDE,
    ]
    assert trace.total_steps == 4
    assert trace.confidence == pytest.approx(0.88, rel=1e-2)
    assert any(obs.result.get("mode") == "path" for obs in trace.observations)


async def test_verification_flow() -> None:
    fact = ExtractedFact(
        fact_id="fact-1",
        content="Policy Alpha increased coverage in 2023.",
        fact_type=FactType.RELATION,
        subject="Policy Alpha",
        predicate="increased",
        object="coverage",
        source_span=(0, 35),
    )
    verifier = FactVerifier(kg_client=EvidenceKG(), llm_backend=SequencedLLM("LLM summary."))
    result = await verifier.verify(fact)

    recorder = TraceRecorder()
    source = recorder.record_node("observation", fact.content, result.confidence, ["kg:1"])
    conclusion = recorder.record_node(
        "conclusion",
        result.explanation,
        0.9,
        [],
    )
    recorder.record_edge(source, conclusion, "supports", 0.4)
    trace = recorder.build_trace("Verify Policy Alpha claim")

    generator = VisualizationDataGenerator()
    trace_graph = generator.from_trace(trace)
    report = ReportGenerator().generate([result], answer_id="answer-1")
    report_graph = generator.from_verification(report)
    store = VisualizationMemoryStore()
    store.set_trace(trace)
    store.set_report(report)
    fact_context = await store.get_node_context("fact:fact-1")

    assert trace_graph.nodes and trace_graph.edges
    assert report_graph.nodes[0].metadata["verified"] == report.verified_count
    assert fact_context["metadata"]["status"] in {"verified", "partial"}


async def test_full_pipeline(tmp_path: Path) -> None:
    parser_payload = json.dumps(
        {
            "intent": "compare",
            "entities": [
                {"text": "Policy Alpha", "type": "POLICY", "start": 0, "end": 12},
                {"text": "Policy Beta", "type": "POLICY", "start": 17, "end": 28},
            ],
            "constraints": [
                {"field": "year", "operator": "between", "value": ["2022", "2023"]},
            ],
            "complexity": 3,
        }
    )
    parser = QueryParser(backend=SequencedLLM(parser_payload))
    linker = EntityLinker(similarity_threshold=0.2, max_alternatives=2)
    planner = QueryPlanner(id_factory=lambda: "plan-complete")
    kg_builder = DummyKGBuilder()
    engine = QueryEngine(
        data_processor=DataProcessor(),
        kg_builder=kg_builder,
        hallucination_guard=HallucinationGuard(),
    )

    query = "Compare Policy Alpha and Policy Beta signals between 2022 and 2023."
    parsed = await parser.parse(query)
    linked = await linker.link(parsed.entities, kg_builder)
    plan = await planner.plan(parsed, linked)

    cypher_query = CypherGenerator(default_timeout=0.0).from_plan(plan)
    executor = CypherExecutor(
        DummyNeo4jClient(),
        settings=CypherExecutorSettings(timeout=0.0, max_retries=0),
    )
    cypher_result = await executor.execute(cypher_query)
    orchestrated = await engine.query(query)

    reasoning_backend = SequencedLLM(
        [
            json.dumps(
                {
                    "reasoning": "Search KG for Alpha evidence.",
                    "action": "search",
                    "action_input": {"question": "Policy Alpha performance"},
                }
            ),
            json.dumps(
                {
                    "reasoning": "Conclude with comparative insight.",
                    "action": "conclude",
                    "action_input": {
                        "confidence": 0.75,
                        "source_queries": ["Policy Alpha performance"],
                    },
                }
            ),
        ]
    )
    agent = ReActAgent(
        kg_builder=kg_builder,
        llm_backend=reasoning_backend,
        settings=ReActSettings(max_iterations=3, timeout_per_step=1.0),
    )
    react_trace = await agent.reason(query)

    fact = ExtractedFact(
        fact_id="fact-full",
        content="Policy Alpha outperformed Policy Beta in 2023.",
        fact_type=FactType.RELATION,
        subject="Policy Alpha",
        predicate="outperformed",
        object="Policy Beta",
        source_span=(0, 45),
    )
    verifier = FactVerifier(
        kg_client=EvidenceKG(),
        llm_backend=SequencedLLM("Alpha outperform statement verified."),
    )
    verification_result = await verifier.verify(fact)
    report = ReportGenerator().generate([verification_result], answer_id="answer-42")
    viz_generator = VisualizationDataGenerator()
    viz_payload = viz_generator.to_d3_json(viz_generator.from_verification(report))

    assert parsed.intent is QueryIntent.COMPARE
    assert cypher_result.nodes
    assert orchestrated.startswith("mix:")
    assert react_trace.final_answer
    assert viz_payload["stats"]["nodes"] >= 2
