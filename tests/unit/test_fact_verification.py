"""Tests covering fact extraction, verification, and reporting."""

from __future__ import annotations

import pytest

from epip.core.llm_backend import LLMBackend
from epip.verification import (
    Evidence,
    ExtractedFact,
    FactExtractor,
    FactType,
    FactVerifier,
    ReportGenerator,
    VerificationResult,
    VerificationStatus,
)


class DummyLLM(LLMBackend):
    """Stubbed backend returning deterministic explanations."""

    async def generate(self, prompt: str, **_: object) -> str:
        assert "Fact" in prompt
        return "LLM summary."


class DummyKG:
    """Stub KG client returning high-confidence evidence."""

    async def find_fact_evidence(self, fact: ExtractedFact):
        assert fact.fact_id == "fact-1"
        return [
            {
                "source_type": "kg_node",
                "source_id": "node-1",
                "content": "KG confirms the reported value.",
                "confidence": 0.92,
            }
        ]


def build_fact(
    fact_id: str = "fact-1",
    content: str = "Hospital visits reached 120.",
) -> ExtractedFact:
    return ExtractedFact(
        fact_id=fact_id,
        content=content,
        fact_type=FactType.NUMERIC,
        subject="Hospital visits",
        predicate="reached",
        object="120",
        source_span=(0, len(content)),
    )


def build_result(
    fact: ExtractedFact,
    status: VerificationStatus,
    confidence: float,
) -> VerificationResult:
    ev = Evidence(source_type="kg_node", source_id="e-1", content="evidence", confidence=confidence)
    return VerificationResult(
        fact=fact,
        status=status,
        confidence=confidence,
        evidences=[ev],
        conflicts=[],
        explanation="",
    )


def test_fact_extractor_extracts_sentences():
    text = "医院在2023年共接待120万患者。护士团队超过5000人。"
    extractor = FactExtractor(id_factory=lambda index: f"t-{index}")

    facts = extractor.extract(text)

    assert len(facts) == 2
    assert facts[0].fact_id == "t-1"
    assert facts[0].fact_type in (FactType.TEMPORAL, FactType.NUMERIC)
    assert facts[0].subject
    assert facts[1].fact_type is FactType.NUMERIC


def test_fact_extractor_decomposes_composite_fact():
    extractor = FactExtractor()
    fact = ExtractedFact(
        fact_id="fact-1",
        content="Hospital A increased beds and expanded ICU capacity",
        fact_type=FactType.COMPOSITE,
        subject="Hospital A",
        predicate="",
        object=None,
        source_span=(0, 52),
    )

    sub_facts = extractor.decompose_composite(fact)

    assert len(sub_facts) == 2
    assert sub_facts[0].fact_id == "fact-1.1"
    assert sub_facts[0].subject == "Hospital A"
    assert sub_facts[1].fact_type in (FactType.ATTRIBUTE, FactType.NUMERIC)


@pytest.mark.asyncio
async def test_fact_verifier_verify_marks_fact_as_verified():
    fact = build_fact()
    verifier = FactVerifier(kg_client=DummyKG(), llm_backend=DummyLLM())

    result = await verifier.verify(fact)

    assert result.status is VerificationStatus.VERIFIED
    assert result.confidence == pytest.approx(0.92, rel=1e-2)
    assert result.evidences
    assert "LLM" in result.explanation


def test_report_generator_filters_weak_facts():
    generator = ReportGenerator()
    strong_fact = build_fact("fact-strong", "Admissions grew 10%.")
    weak_fact = build_fact("fact-weak", "Satisfaction reached 30%.")
    strong_result = build_result(strong_fact, VerificationStatus.VERIFIED, 0.9)
    weak_result = build_result(weak_fact, VerificationStatus.UNVERIFIED, 0.5)

    strong, weak = generator.filter_weak_facts([strong_result, weak_result], threshold=0.8)

    assert len(strong) == 1
    assert strong[0].fact.fact_id == "fact-strong"
    assert weak == [weak_fact]


def test_report_generator_to_markdown_includes_summary():
    generator = ReportGenerator()
    fact = build_fact("fact-strong", "Admissions grew 10%.")
    low_fact = build_fact("fact-weak", "Satisfaction reached 30%.")
    results = [
        build_result(fact, VerificationStatus.VERIFIED, 0.9),
        build_result(low_fact, VerificationStatus.UNVERIFIED, 0.4),
    ]
    report = generator.generate(results, answer_id="answer-1")

    markdown = generator.to_markdown(report)

    assert "# Verification Report for answer-1" in markdown
    assert "| fact-strong | verified |" in markdown
    assert "Filtered low-confidence facts" in markdown
    assert "fact-weak" in markdown
