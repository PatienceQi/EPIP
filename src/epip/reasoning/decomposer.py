"""Query decomposition utilities powering the ReAct reasoning loop."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

_SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？?!；;]+")
_PARALLEL_SPLIT_PATTERN = re.compile(r"\b(?:and|以及|同时|并且)\b", re.IGNORECASE)


@dataclass(slots=True)
class SubQuery:
    """Atomic question extracted from a complex query."""

    id: str
    question: str
    depends_on: list[str] = field(default_factory=list)
    priority: int = 0


@dataclass(slots=True)
class DecomposedQuery:
    """Decomposition output with execution plan metadata."""

    original: str
    sub_queries: list[SubQuery]
    execution_order: list[list[str]]


class QueryDecomposer:
    """Break down user queries into manageable sub-questions."""

    def __init__(self, *, min_subqueries: int = 3, max_subqueries: int = 5) -> None:
        self._min_subqueries = max(1, min_subqueries)
        self._max_subqueries = max(self._min_subqueries, max_subqueries)

    async def decompose(self, query: str) -> DecomposedQuery:
        """Decompose a complex query into prioritized sub-queries."""
        text = query.strip()
        if not text:
            raise ValueError("Query text cannot be empty.")

        clauses = self._split_into_clauses(text)
        clauses = self._pad_clauses(text, clauses)

        sub_queries: list[SubQuery] = []
        issued_ids: list[str] = []

        for index, clause in enumerate(clauses, start=1):
            sub_id = f"sub-{index}"
            depends_on = self._infer_dependencies(clause, issued_ids)
            sub_queries.append(
                SubQuery(
                    id=sub_id,
                    question=clause,
                    depends_on=depends_on,
                    priority=index,
                )
            )
            issued_ids.append(sub_id)

        execution_order = self.build_execution_plan(sub_queries)
        logger.debug(
            "Decomposed query",
            original=text,
            plan_layers=len(execution_order),
            sub_queries=len(sub_queries),
        )
        return DecomposedQuery(
            original=text,
            sub_queries=sub_queries,
            execution_order=execution_order,
        )

    def build_execution_plan(self, sub_queries: list[SubQuery]) -> list[list[str]]:
        """Create a layered execution plan using topological ordering."""
        indegree: dict[str, int] = {sub.id: len(sub.depends_on) for sub in sub_queries}
        dependents: dict[str, list[str]] = {sub.id: [] for sub in sub_queries}
        for sub in sub_queries:
            for dependency in sub.depends_on:
                if dependency in dependents:
                    dependents[dependency].append(sub.id)

        layers: list[list[str]] = []
        available = sorted(
            (sub.id for sub in sub_queries if indegree[sub.id] == 0),
            key=lambda node: self._priority_for(node, sub_queries),
        )
        processed: set[str] = set()

        while available:
            current_layer = available
            layers.append(current_layer)
            next_candidates: set[str] = set()
            for node in current_layer:
                processed.add(node)
                for neighbor in dependents.get(node, []):
                    indegree[neighbor] -= 1
                    if indegree[neighbor] == 0:
                        next_candidates.add(neighbor)
            available = sorted(
                next_candidates,
                key=lambda node: self._priority_for(node, sub_queries),
            )

        if len(processed) != len(sub_queries):
            missing = {sub.id for sub in sub_queries} - processed
            logger.warning("Cycle detected while building execution plan", missing=sorted(missing))
            raise ValueError("Cycle detected in sub-query dependencies.")

        return layers

    def _split_into_clauses(self, query: str) -> list[str]:
        clauses = []
        for sentence in _SENTENCE_SPLIT_PATTERN.split(query):
            cleaned = sentence.strip(" ,;；")
            if not cleaned:
                continue
            fragments = _PARALLEL_SPLIT_PATTERN.split(cleaned)
            for fragment in fragments:
                candidate = fragment.strip(" ,;；")
                if candidate:
                    clauses.append(candidate)
        return clauses

    def _pad_clauses(self, original: str, clauses: list[str]) -> list[str]:
        clauses = list(dict.fromkeys(clauses))  # Preserve order while removing duplicates.
        while len(clauses) > self._max_subqueries:
            clauses[-2] = f"{clauses[-2]} and {clauses[-1]}"
            clauses.pop()
        templates = [
            "Identify key drivers related to {query}",
            "Evaluate time-based changes affecting {query}",
            "Summarize policy implications for {query}",
        ]
        template_index = 0
        while len(clauses) < self._min_subqueries:
            template = templates[template_index % len(templates)]
            clauses.append(template.format(query=original))
            template_index += 1
        return clauses

    def _infer_dependencies(self, clause: str, issued_ids: list[str]) -> list[str]:
        if not issued_ids:
            return []
        lowered = clause.lower()
        depends_on: list[str] = []
        if any(keyword in lowered for keyword in ("overall", "conclude", "final", "impact")):
            depends_on = list(issued_ids)
        elif any(
            keyword in lowered for keyword in ("after", "based on", "using previous", "derive")
        ):
            depends_on = [issued_ids[-1]]
        return depends_on

    @staticmethod
    def _priority_for(node_id: str, sub_queries: list[SubQuery]) -> int:
        priority_lookup = {sub.id: sub.priority for sub in sub_queries}
        return priority_lookup.get(node_id, 0)
