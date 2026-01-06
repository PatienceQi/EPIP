"""Fact extraction utilities for the verification pipeline."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class FactType(str, Enum):
    """Supported fact categories used during verification."""

    NUMERIC = "numeric"
    TEMPORAL = "temporal"
    RELATION = "relation"
    ATTRIBUTE = "attribute"
    COMPOSITE = "composite"


@dataclass(slots=True)
class ExtractedFact:
    """Normalized representation of a fact mentioned in the answer text."""

    fact_id: str
    content: str
    fact_type: FactType
    subject: str
    predicate: str | None
    object: str | None
    source_span: tuple[int, int]
    sub_facts: list[ExtractedFact] = field(default_factory=list)


_SENTENCE_PATTERN = re.compile(r"[^。！？!?]+(?:[。！？!?]+|$)")
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_TEMPORAL_PATTERN = re.compile(r"((?:19|20)\d{2}|\d{4}年|\d{1,2}月)")
_COMPOSITE_SPLIT_PATTERN = re.compile(
    r"\s*(?:\band\b|\bor\b|以及|并且|且|、|;|；)\s*",
    re.IGNORECASE,
)
_COMPOSITE_HINT_PATTERN = re.compile(r"\b(?:and|or)\b|以及|并且|且|、|;|；", re.IGNORECASE)


class FactExtractor:
    """Extracts verifiable statements from natural language answers."""

    DEFAULT_PROMPT = (
        "Identify verifiable facts in the provided answer. "
        "For each fact return JSON entries with fields: "
        '{"content": "...", "subject": "...", "predicate": "...", "object": "..."}'
    )

    def __init__(
        self,
        *,
        id_factory: Callable[[int], str] | None = None,
        llm_callable: Callable[[str, str], str] | None = None,
        llm_prompt: str | None = None,
    ) -> None:
        self._id_factory = id_factory or (lambda index: f"fact-{index}")
        self._llm_callable = llm_callable
        self._llm_prompt = llm_prompt or self.DEFAULT_PROMPT

    def extract(self, text: str) -> list[ExtractedFact]:
        """Return the list of facts parsed from ``text`` using LLM and heuristics."""

        if not text or not text.strip():
            return []

        llm_facts = self._request_llm(text) if self._llm_callable else None
        if llm_facts:
            facts = self._build_facts_from_payload(llm_facts, text)
        else:
            facts = []

        if not facts:
            for index, (sentence, span) in enumerate(self._split_sentences(text), start=1):
                subject, predicate, obj = self._infer_spo(sentence)
                fact = ExtractedFact(
                    fact_id=self._id_factory(index),
                    content=sentence,
                    fact_type=self.classify_fact_type(sentence),
                    subject=subject or "",
                    predicate=predicate,
                    object=obj,
                    source_span=span,
                )
                if fact.fact_type is FactType.COMPOSITE:
                    fact.sub_facts = self.decompose_composite(fact)
                facts.append(fact)
        return facts

    def _request_llm(self, text: str) -> list[dict[str, str]] | None:
        try:
            response = self._llm_callable(text, self._llm_prompt)  # type: ignore[misc]
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Fact extraction LLM call failed", error=str(exc))
            return None
        candidate = str(response).strip()
        if not candidate:
            return None
        payload: list[dict[str, str]] | None = None
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                payload = parsed.get("facts")
            elif isinstance(parsed, list):
                payload = parsed
        except json.JSONDecodeError:
            logger.debug("LLM fact extraction returned non-JSON", output=candidate)
            return None
        if not payload:
            return None
        return [entry for entry in payload if isinstance(entry, dict)]

    def _build_facts_from_payload(
        self,
        payload: Iterable[dict[str, str]],
        text: str,
    ) -> list[ExtractedFact]:
        facts: list[ExtractedFact] = []
        index = 1
        for entry in payload:
            content = entry.get("content", "").strip()
            if not content:
                continue
            span = self._locate_span(text, content)
            subject = entry.get("subject") or ""
            predicate = entry.get("predicate")
            obj = entry.get("object")
            fact = ExtractedFact(
                fact_id=self._id_factory(index),
                content=content,
                fact_type=self.classify_fact_type(content),
                subject=subject,
                predicate=predicate,
                object=obj,
                source_span=span,
            )
            if fact.fact_type is FactType.COMPOSITE:
                fact.sub_facts = self.decompose_composite(fact)
            facts.append(fact)
            index += 1
        return facts

    @staticmethod
    def _locate_span(text: str, snippet: str) -> tuple[int, int]:
        normalized = snippet.strip()
        if not normalized:
            return (0, 0)
        start = text.find(normalized)
        if start >= 0:
            end = start + len(normalized)
            return (start, end)
        return (0, len(normalized))

    def decompose_composite(self, fact: ExtractedFact) -> list[ExtractedFact]:
        """Split a composite fact into atomic statements."""

        segments = [segment.strip() for segment in _COMPOSITE_SPLIT_PATTERN.split(fact.content)]
        segments = [segment for segment in segments if segment]
        if len(segments) <= 1:
            return []

        sub_facts: list[ExtractedFact] = []
        cursor = 0
        for index, segment in enumerate(segments, start=1):
            relative_start = fact.content.find(segment, cursor)
            if relative_start >= 0:
                start = fact.source_span[0] + relative_start
                end = start + len(segment)
                cursor = relative_start + len(segment)
            else:  # pragma: no cover - defensive fallback for malformed spans
                start, end = fact.source_span
            subject, predicate, obj = self._infer_spo(segment)
            subject_value = fact.subject if fact.subject else subject or ""
            sub_fact = ExtractedFact(
                fact_id=f"{fact.fact_id}.{index}",
                content=segment,
                fact_type=self.classify_fact_type(segment),
                subject=subject_value,
                predicate=predicate or fact.predicate,
                object=obj or fact.object,
                source_span=(start, end),
            )
            sub_facts.append(sub_fact)
        return sub_facts

    def classify_fact_type(self, fact: ExtractedFact | str) -> FactType:
        """Categorize the supplied fact text into one of the supported classes."""

        content = fact.content if isinstance(fact, ExtractedFact) else str(fact)
        normalized = content.strip()
        if not normalized:
            return FactType.ATTRIBUTE

        lowered = normalized.lower()
        if _COMPOSITE_HINT_PATTERN.search(normalized) and len(
            [p for p in _COMPOSITE_SPLIT_PATTERN.split(normalized) if p.strip()]
        ) > 1:
            return FactType.COMPOSITE
        if _TEMPORAL_PATTERN.search(normalized):
            return FactType.TEMPORAL
        if _NUMBER_PATTERN.search(normalized):
            return FactType.NUMERIC
        relation_keywords = ("between", "relationship", "linked", "connect", "与", "和", "关系")
        if any(keyword in lowered for keyword in relation_keywords):
            return FactType.RELATION
        attribute_markers = (" is ", " are ", " 位于", " 属于", "拥有", "has", "include")
        if any(marker in lowered for marker in attribute_markers):
            return FactType.ATTRIBUTE
        return FactType.ATTRIBUTE

    def _split_sentences(self, text: str) -> list[tuple[str, tuple[int, int]]]:
        sentences: list[tuple[str, tuple[int, int]]] = []
        for match in _SENTENCE_PATTERN.finditer(text):
            start, end = match.span()
            segment = match.group().strip()
            if not segment:
                continue
            start, end = self._trim_span(text, start, end)
            sentences.append((segment, (start, end)))
        return sentences

    @staticmethod
    def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    @staticmethod
    def _infer_spo(sentence: str) -> tuple[str, str | None, str | None]:
        normalized = sentence.strip()
        lowered = normalized.lower()
        copulas = [" is ", " are ", " was ", " were ", " has ", " have ", " include "]
        for copula in copulas:
            if copula in lowered:
                pivot = lowered.index(copula)
                subject = normalized[:pivot].strip(", ")
                obj = normalized[pivot + len(copula) :].strip(", . \"'")
                return subject, copula.strip(), obj or None

        chinese_markers = ("是", "为", "位于", "包含", "包括", "拥有", "达到")
        for marker in chinese_markers:
            pivot = normalized.find(marker)
            if pivot > 0:
                subject = normalized[:pivot].strip()
                obj = normalized[pivot + len(marker) :].strip()
                return subject, marker, obj or None

        tokens = normalized.split()
        if len(tokens) >= 3:
            subject = tokens[0]
            predicate = tokens[1]
            obj = " ".join(tokens[2:])
            return subject, predicate, obj
        if len(tokens) == 2:
            return tokens[0], None, tokens[1]
        return normalized, None, None
