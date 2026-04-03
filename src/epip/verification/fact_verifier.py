"""Knowledge-graph backed fact verification utilities."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from epip.core.llm_backend import LLMBackend

from .fact_extractor import ExtractedFact

logger = structlog.get_logger(__name__)


class VerificationStatus(str, Enum):
    """Supported verification outcomes for extracted facts."""

    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partial"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


@dataclass(slots=True)
class Evidence:
    """Supporting or contradicting evidence."""

    source_type: str
    source_id: str
    content: str
    confidence: float


@dataclass(slots=True)
class VerificationResult:
    """Result produced after validating a single fact."""

    fact: ExtractedFact
    status: VerificationStatus
    confidence: float
    evidences: list[Evidence] = field(default_factory=list)
    conflicts: list[Evidence] = field(default_factory=list)
    explanation: str = ""


class FactVerifier:
    """Validates extracted facts by cross-checking KG evidence and LLM signals."""

    def __init__(
        self,
        kg_client: Any,
        llm_backend: LLMBackend | None,
        *,
        evidence_limit: int = 5,
    ) -> None:
        self._kg_client = kg_client
        self._llm_backend = llm_backend
        self._evidence_limit = max(1, evidence_limit)

    async def verify(self, fact: ExtractedFact) -> VerificationResult:
        """Verify a single fact and return a structured result."""

        evidences = await self.find_kg_evidence(fact)
        conflicts = [ev for ev in evidences if ev.source_type == "conflict" or ev.confidence < 0]
        supporting = [ev for ev in evidences if ev not in conflicts]
        confidence = self.calculate_confidence(supporting)

        if supporting and not conflicts and confidence >= 0.85:
            status = VerificationStatus.VERIFIED
        elif supporting and (confidence >= 0.5 or conflicts):
            status = VerificationStatus.PARTIALLY_VERIFIED
        elif conflicts and not supporting:
            status = VerificationStatus.CONTRADICTED
        else:
            status = VerificationStatus.UNVERIFIED
            confidence = 0.0

        explanation = await self._build_explanation(fact, status, supporting, conflicts)
        return VerificationResult(
            fact=fact,
            status=status,
            confidence=min(max(confidence, 0.0), 1.0),
            evidences=supporting,
            conflicts=conflicts,
            explanation=explanation,
        )

    async def verify_batch(self, facts: list[ExtractedFact]) -> list[VerificationResult]:
        """Verify a collection of facts concurrently."""

        if not facts:
            return []
        tasks = [self.verify(fact) for fact in facts]
        return await asyncio.gather(*tasks)

    async def find_kg_evidence(self, fact: ExtractedFact) -> list[Evidence]:
        """Search the knowledge graph for supporting evidence."""

        if not self._kg_client:
            return []

        handler = self._resolve_handler()
        if handler is None:
            return []

        try:
            result = handler(fact)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("KG evidence lookup failed", error=str(exc))
            return []

        return self._normalize_evidence(result)

    def calculate_confidence(self, evidences: Iterable[Evidence]) -> float:
        """Aggregate multiple evidence confidences."""

        evidence_list = list(evidences)
        if not evidence_list:
            return 0.0
        total = sum(min(max(ev.confidence, 0.0), 1.0) for ev in evidence_list)
        return total / len(evidence_list)

    def _resolve_handler(self) -> Any | None:
        for attr in ("find_fact_evidence", "search_fact", "query_fact"):
            if hasattr(self._kg_client, attr):
                return getattr(self._kg_client, attr)
        return None

    def _normalize_evidence(self, items: Any) -> list[Evidence]:
        normalized: list[Evidence] = []
        if not items:
            return normalized
        iterable: Iterable[Any]
        if isinstance(items, Evidence):
            iterable = [items]
        elif isinstance(items, dict):
            iterable = [items]
        else:
            if isinstance(items, str):
                iterable = [items]
            else:
                try:
                    iterable = list(items)
                except TypeError:
                    iterable = [items]
        for entry in iterable:
            if isinstance(entry, Evidence):
                normalized.append(entry)
                continue
            if not isinstance(entry, dict):
                continue
            source_type = str(entry.get("source_type", "kg_node"))
            source_id = str(entry.get("source_id", "")) or "unknown"
            content = str(entry.get("content", ""))
            confidence = float(entry.get("confidence", 0.0))
            normalized.append(
                Evidence(
                    source_type=source_type,
                    source_id=source_id,
                    content=content,
                    confidence=confidence,
                )
            )
            if len(normalized) >= self._evidence_limit:
                break
        return normalized

    async def _build_explanation(
        self,
        fact: ExtractedFact,
        status: VerificationStatus,
        evidences: list[Evidence],
        conflicts: list[Evidence],
    ) -> str:
        summary = (
            f"Fact '{fact.content}' classified as {status.value} with {len(evidences)} "
            f"supporting evidence(s) and {len(conflicts)} conflict(s)."
        )
        if not self._llm_backend:
            return summary
        prompt = (
            "You are auditing factual statements against a knowledge graph. "
            "Summarize the verification outcome in 1-2 sentences.\n"
            f"Fact: {fact.content}\n"
            f"Status: {status.value}\n"
            f"Supporting evidence: " + "; ".join(ev.content for ev in evidences[:3]) + "\n"
            "Conflicts: " + ("; ".join(ev.content for ev in conflicts[:3]) or "None")
        )
        try:
            response = await self._llm_backend.generate(
                prompt,
                max_tokens=160,
                temperature=0.0,
            )
            cleaned = response.strip()
            return cleaned or summary
        except Exception as exc:  # pragma: no cover - network/LLM dependent
            logger.warning("LLM explanation generation failed", error=str(exc))
            return summary
