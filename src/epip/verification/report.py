"""Verification reporting utilities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from .fact_extractor import ExtractedFact
from .fact_verifier import VerificationResult, VerificationStatus


class ConfidenceLevel(str, Enum):
    """Confidence levels derived from aggregated scores."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_score(cls, value: float) -> ConfidenceLevel:
        if value >= 0.85:
            return cls.HIGH
        if value >= 0.7:
            return cls.MEDIUM
        return cls.LOW


@dataclass(slots=True)
class VerificationReport:
    """Aggregated verification report for an answer."""

    answer_id: str
    total_facts: int
    verified_count: int
    partial_count: int
    unverified_count: int
    contradicted_count: int
    overall_confidence: float
    results: list[VerificationResult] = field(default_factory=list)
    filtered_facts: list[ExtractedFact] = field(default_factory=list)


class ReportGenerator:
    """Utility class that aggregates verification outputs."""

    def __init__(self, *, weak_threshold: float = 0.7) -> None:
        self._weak_threshold = weak_threshold

    def generate(
        self,
        results: list[VerificationResult],
        *,
        answer_id: str = "answer-unknown",
    ) -> VerificationReport:
        total = len(results)
        verified = sum(1 for result in results if result.status is VerificationStatus.VERIFIED)
        partial = sum(
            1 for result in results if result.status is VerificationStatus.PARTIALLY_VERIFIED
        )
        unverified = sum(1 for result in results if result.status is VerificationStatus.UNVERIFIED)
        contradicted = sum(
            1 for result in results if result.status is VerificationStatus.CONTRADICTED
        )
        overall = self._average_confidence(results)
        _, weak_facts = self.filter_weak_facts(results, threshold=self._weak_threshold)
        return VerificationReport(
            answer_id=answer_id,
            total_facts=total,
            verified_count=verified,
            partial_count=partial,
            unverified_count=unverified,
            contradicted_count=contradicted,
            overall_confidence=overall,
            results=list(results),
            filtered_facts=weak_facts,
        )

    def filter_weak_facts(
        self,
        results: Iterable[VerificationResult],
        threshold: float = 0.7,
    ) -> tuple[list[VerificationResult], list[ExtractedFact]]:
        strong: list[VerificationResult] = []
        weak: list[ExtractedFact] = []
        for result in results:
            if result.confidence >= threshold:
                strong.append(result)
                continue
            weak.append(result.fact)
        return strong, weak

    def to_markdown(self, report: VerificationReport) -> str:
        lines = [
            f"# Verification Report for {report.answer_id}",
            "",
            f"- Total facts: {report.total_facts}",
            f"- Verified: {report.verified_count}",
            f"- Partially verified: {report.partial_count}",
            f"- Unverified: {report.unverified_count}",
            f"- Contradicted: {report.contradicted_count}",
            f"- Overall confidence: {report.overall_confidence:.2f} "
            f"({ConfidenceLevel.from_score(report.overall_confidence).value})",
            "",
            "| Fact ID | Status | Confidence | Evidence |",
            "| --- | --- | --- | --- |",
        ]
        for result in report.results:
            level = ConfidenceLevel.from_score(result.confidence).value
            lines.append(
                f"| {result.fact.fact_id} | {result.status.value} | "
                f"{result.confidence:.2f} ({level}) | {len(result.evidences)} |"
            )
        if report.filtered_facts:
            lines.append("")
            lines.append("## Filtered low-confidence facts")
            for fact in report.filtered_facts:
                lines.append(f"- {fact.fact_id}: {fact.content}")
        return "\n".join(lines)

    def to_json(self, report: VerificationReport) -> dict:
        return {
            "answer_id": report.answer_id,
            "total_facts": report.total_facts,
            "verified_count": report.verified_count,
            "partial_count": report.partial_count,
            "unverified_count": report.unverified_count,
            "contradicted_count": report.contradicted_count,
            "overall_confidence": report.overall_confidence,
            "confidence_level": ConfidenceLevel.from_score(report.overall_confidence).value,
            "results": [
                {
                    "fact_id": result.fact.fact_id,
                    "content": result.fact.content,
                    "status": result.status.value,
                    "confidence": result.confidence,
                    "evidence": [
                        {
                            "source_type": evidence.source_type,
                            "source_id": evidence.source_id,
                            "content": evidence.content,
                            "confidence": evidence.confidence,
                        }
                        for evidence in result.evidences
                    ],
                    "conflicts": [
                        {
                            "source_type": conflict.source_type,
                            "source_id": conflict.source_id,
                            "content": conflict.content,
                            "confidence": conflict.confidence,
                        }
                        for conflict in result.conflicts
                    ],
                }
                for result in report.results
            ],
            "filtered_facts": [
                {"fact_id": fact.fact_id, "content": fact.content} for fact in report.filtered_facts
            ],
        }

    @staticmethod
    def _average_confidence(results: Iterable[VerificationResult]) -> float:
        total = 0.0
        count = 0
        for result in results:
            total += max(0.0, min(1.0, result.confidence))
            count += 1
        return total / count if count else 0.0
