"""Natural language query parsing powered by the shared LLM backend."""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from epip.config import LightRAGConfig
from epip.core.llm_backend import LLMBackend, create_llm_backend

logger = structlog.get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are an assistant that converts natural language questions into structured "
    "representations for a knowledge graph. Always respond with compact JSON using the "
    "following schema:\n"
    "{\n"
    '  "intent": "fact|relation|path|aggregate|compare",\n'
    '  "entities": [\n'
    '    {"text": "...", "type": "ORGANIZATION", "start": 0, "end": 5}\n'
    "  ],\n"
    '  "constraints": [\n'
    '    {"field": "time", "operator": "between", "value": ["2020", "2023"]}\n'
    "  ],\n"
    '  "complexity": 1\n'
    "}\n"
    "Use zero-based indices for entity spans. Keep arrays short (<=5 items) and omit nulls."
)

ConstraintValue = str | list[str] | list[int] | list[float] | dict[str, Any] | float | int


class QueryIntent(str, Enum):
    """Supported intent labels for natural language queries."""

    FACT = "fact"
    RELATION = "relation"
    PATH = "path"
    AGGREGATE = "aggregate"
    COMPARE = "compare"


@dataclass(slots=True)
class EntityMention:
    """Span representing an entity mention detected in the query text."""

    text: str
    entity_type: str | None
    start: int
    end: int


@dataclass(slots=True)
class QueryConstraint:
    """Structured filter extracted from the natural language query."""

    field: str
    operator: str
    value: ConstraintValue


@dataclass(slots=True)
class ParsedQuery:
    """Normalized representation of the original natural language question."""

    original: str
    intent: QueryIntent
    entities: list[EntityMention] = field(default_factory=list)
    constraints: list[QueryConstraint] = field(default_factory=list)
    complexity: int = 1


_CAPITALIZED_PATTERN = re.compile(r"\b([A-Z][\w]*(?:\s+[A-Z][\w]*)*)")
_CHINESE_PATTERN = re.compile(r"([\u4e00-\u9fff]{2,})")
_YEAR_PATTERN = re.compile(r"(20\d{2}|19\d{2})")
_RANGE_PATTERN = re.compile(
    r"(?:between|from)\s+(?P<start>\d{4})\s+(?:and|to)\s+(?P<end>\d{4})", re.IGNORECASE
)
_LOCATION_PATTERN = re.compile(r"(?:in|within)\s+(?P<location>[A-Z][\w\s]+)")


class QueryParser:
    """LLM-backed query parser with lightweight heuristic fallbacks."""

    def __init__(
        self,
        backend: LLMBackend | None = None,
        *,
        config: LightRAGConfig | None = None,
        system_prompt: str | None = None,
        cache_size: int = 32,
    ) -> None:
        self._backend = backend
        self._config = config or LightRAGConfig()
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._cache_size = max(1, cache_size)
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

    async def parse(self, query: str) -> ParsedQuery:
        """Return structured representation of the question."""
        query = query.strip()
        if not query:
            raise ValueError("Query text cannot be empty.")
        payload = await self._analyze(query)
        return self._build_parsed_query(query, payload)

    async def extract_entities(self, query: str) -> list[EntityMention]:
        """Shortcut helper that exposes only the entity mentions."""
        return (await self.parse(query)).entities

    async def classify_intent(self, query: str) -> QueryIntent:
        """Return the dominant intent for the supplied query."""
        return (await self.parse(query)).intent

    async def _analyze(self, query: str) -> dict[str, Any]:
        cached = self._cache.get(query)
        if cached:
            self._cache.move_to_end(query)
            return cached

        payload = await self._request_llm(query)
        if not payload:
            payload = self._heuristic_parse(query)
        self._cache[query] = payload
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return payload

    async def _request_llm(self, query: str) -> dict[str, Any] | None:
        backend = self._require_backend()
        prompt = self._build_prompt(query)
        try:
            response = await backend.generate(
                prompt,
                system_prompt=self._system_prompt,
                max_tokens=600,
                temperature=0.0,
            )
        except Exception as exc:  # pragma: no cover - defensive, network dependent
            logger.warning("LLM query parsing failed; using heuristics", error=str(exc))
            return None
        return self._parse_llm_payload(response)

    def _require_backend(self) -> LLMBackend:
        if self._backend is None:
            self._backend = create_llm_backend(self._config)
        return self._backend

    @staticmethod
    def _build_prompt(query: str) -> str:
        normalized = query.strip()
        return (
            "Analyze the following user question and convert it to structured JSON. "
            "Include at most five entities and constraints.\n"
            f"Question: {normalized}"
        )

    def _parse_llm_payload(self, response: str) -> dict[str, Any] | None:
        candidate = response.strip()
        if not candidate:
            return None
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            candidate = candidate.replace("json", "", 1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", response, flags=re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.debug("Failed to decode LLM parser output", output=response)
                return None

    def _build_parsed_query(self, query: str, payload: dict[str, Any]) -> ParsedQuery:
        intent_label = payload.get("intent")
        intent = self._coerce_intent(intent_label)
        entities = self._convert_entities(payload.get("entities") or [], query)
        constraints = self._convert_constraints(payload.get("constraints") or [])
        complexity = self._determine_complexity(
            payload.get("complexity"),
            intent,
            entities,
            constraints,
            query,
        )
        return ParsedQuery(
            original=query,
            intent=intent,
            entities=entities,
            constraints=constraints,
            complexity=complexity,
        )

    @staticmethod
    def _coerce_intent(label: Any) -> QueryIntent:
        if isinstance(label, str):
            normalized = label.strip().lower()
            for intent in QueryIntent:
                if intent.value == normalized:
                    return intent
        return QueryIntent.FACT

    def _convert_entities(self, items: Sequence[dict[str, Any]], query: str) -> list[EntityMention]:
        mentions: list[EntityMention] = []
        for item in items:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            start = int(item.get("start") or query.find(text))
            end = int(item.get("end") or (start + len(text)))
            entity_type = item.get("type")
            mentions.append(
                EntityMention(
                    text=text,
                    entity_type=str(entity_type) if entity_type else None,
                    start=max(0, start),
                    end=max(0, end),
                )
            )
        if mentions:
            return mentions[:5]
        return self._heuristic_entities(query)

    @staticmethod
    def _convert_constraints(items: Sequence[dict[str, Any]]) -> list[QueryConstraint]:
        constraints: list[QueryConstraint] = []
        for item in items:
            field = str(item.get("field") or "").strip()
            value = item.get("value")
            if not field or value in (None, ""):
                continue
            operator = str(item.get("operator") or "=").lower()
            constraints.append(QueryConstraint(field=field, operator=operator, value=value))
        return constraints[:5]

    def _heuristic_parse(self, query: str) -> dict[str, Any]:
        intent = self._guess_intent(query)
        entities = [
            {
                "text": mention.text,
                "type": mention.entity_type,
                "start": mention.start,
                "end": mention.end,
            }
            for mention in self._heuristic_entities(query)
        ]
        constraints = [
            {"field": constraint.field, "operator": constraint.operator, "value": constraint.value}
            for constraint in self._heuristic_constraints(query)
        ]
        complexity = self._determine_complexity(None, intent, entities, constraints, query)
        return {
            "intent": intent.value,
            "entities": entities,
            "constraints": constraints,
            "complexity": complexity,
        }

    def _heuristic_entities(self, query: str) -> list[EntityMention]:
        mentions: list[EntityMention] = []
        seen_spans: set[tuple[int, int]] = set()

        for pattern in (_CAPITALIZED_PATTERN, _CHINESE_PATTERN):
            for match in pattern.finditer(query):
                text = match.group(1).strip()
                start, end = match.span(1)
                if len(text) < 2:
                    continue
                span = (start, end)
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                entity_type = (
                    "ORGANIZATION" if pattern is _CAPITALIZED_PATTERN else "ENTITY"
                )
                mentions.append(
                    EntityMention(text=text, entity_type=entity_type, start=start, end=end)
                )

        return mentions[:5]

    def _heuristic_constraints(self, query: str) -> list[QueryConstraint]:
        constraints: list[QueryConstraint] = []
        for match in _RANGE_PATTERN.finditer(query):
            start_year = match.group("start")
            end_year = match.group("end")
            constraints.append(
                QueryConstraint(
                    field="time",
                    operator="between",
                    value=[start_year, end_year],
                )
            )

        years = _YEAR_PATTERN.findall(query)
        if years:
            unique_years: list[str] = []
            for year in years:
                if year not in unique_years:
                    unique_years.append(year)
            operator = "in"
            value: ConstraintValue = unique_years
            if len(unique_years) == 1:
                operator = "="
                value = unique_years[0]
            constraints.append(QueryConstraint(field="time", operator=operator, value=value))

        for match in _LOCATION_PATTERN.finditer(query):
            location = match.group("location").strip()
            constraints.append(QueryConstraint(field="location", operator="=", value=location))

        if "女性" in query or "women" in query.lower():
            constraints.append(QueryConstraint(field="demographic", operator="=", value="women"))
        if "男性" in query or "men" in query.lower():
            constraints.append(QueryConstraint(field="demographic", operator="=", value="men"))

        return constraints[:5]

    def _guess_intent(self, query: str) -> QueryIntent:
        normalized = query.lower()
        if any(keyword in normalized for keyword in ("compare", "vs", "差异", "对比")):
            return QueryIntent.COMPARE
        if any(keyword in normalized for keyword in ("shortest path", "路径", "路径上")):
            return QueryIntent.PATH
        if any(keyword in normalized for keyword in ("relate", "关系", "connected")):
            return QueryIntent.RELATION
        aggregate_keywords = ("average", "total", "sum", "多少", "统计", "比例")
        if any(keyword in normalized for keyword in aggregate_keywords):
            return QueryIntent.AGGREGATE
        return QueryIntent.FACT

    def _determine_complexity(
        self,
        supplied: Any,
        intent: QueryIntent,
        entities: Sequence[Any],
        constraints: Sequence[Any],
        query: str,
    ) -> int:
        if isinstance(supplied, (int, float)) and 1 <= int(supplied) <= 5:
            return int(supplied)
        score = 1
        if len(query.split()) > 12:
            score += 1
        if len(entities) > 1:
            score += 1
        if len(constraints) > 1:
            score += 1
        if intent in (QueryIntent.AGGREGATE, QueryIntent.COMPARE, QueryIntent.PATH):
            score += 1
        return max(1, min(5, score))
