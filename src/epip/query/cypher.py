"""Utilities for translating query plans into executable Cypher."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from epip.query.linker import LinkedEntity
from epip.query.parser import QueryConstraint, QueryIntent
from epip.query.planner import QueryPlan

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class CypherQuery:
    """Dataclass describing a Cypher statement and execution metadata."""

    statement: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout: float | None = None
    fallback: CypherQuery | None = None


class CypherGenerator:
    """Generate Cypher statements based on a structured query plan."""

    def __init__(
        self,
        *,
        default_timeout: float = 5.0,
        default_relation: str = "RELATED_TO",
    ) -> None:
        self.default_timeout = default_timeout
        self._default_relation = default_relation
        self._alias_counter = 0
        self._alias_cache: dict[str, str] = {}
        self._where_alias = "n0"
        self._where_params: dict[str, Any] = {}

    def from_plan(self, plan: QueryPlan) -> CypherQuery:
        """Convert a QueryPlan into a single CypherQuery object."""
        self._reset_state()
        parameters: dict[str, Any] = {}
        clauses: list[str] = []

        if not plan.linked_entities:
            logger.warning("Query plan does not contain linked entities", query_id=plan.query_id)
            statement = "MATCH (n) RETURN n LIMIT 25"
            fallback = CypherQuery(
                statement="MATCH (n) RETURN n LIMIT 5",
                timeout=self._fallback_timeout,
            )
            return CypherQuery(
                statement=statement,
                timeout=self.default_timeout,
                fallback=fallback,
            )

        aliases: list[str] = []
        for entity in plan.linked_entities:
            alias = self._alias_for(entity)
            aliases.append(alias)
            clauses.append(self.match_node(entity))
            parameters[f"{alias}_id"] = entity.kg_node_id

        self._where_alias = aliases[0]
        where_clause = self.build_where_clause(plan.parsed.constraints)
        parameters.update(self._where_params)
        self._where_params = {}

        intent = plan.parsed.intent
        return_clause: str
        extra_clauses: list[str] = []

        if intent is QueryIntent.PATH and len(aliases) >= 2:
            max_hops = self._extract_hops(plan)
            extra_clauses.append(self.path_query(aliases[0], aliases[-1], max_hops))
            return_clause = "RETURN path, nodes(path) AS nodes, relationships(path) AS relations"
        elif intent is QueryIntent.RELATION and len(aliases) >= 2:
            relation_type = self._extract_relation(plan)
            extra_clauses.append(self.traverse_relation(aliases[0], aliases[-1], relation_type))
            return_clause = f"RETURN {aliases[0]}, {aliases[-1]}"
        elif intent in (QueryIntent.AGGREGATE, QueryIntent.COMPARE):
            return_clause = f"RETURN count(DISTINCT {aliases[0]}) AS metric"
        else:
            return_clause = f"RETURN {', '.join(aliases)}"

        limit_clause = f"LIMIT {self._determine_limit(plan)}"
        statement_parts = [*clauses, where_clause, *extra_clauses, return_clause, limit_clause]
        statement = "\n".join(part for part in statement_parts if part)

        fallback = CypherQuery(
            statement="MATCH (n) RETURN n LIMIT 5",
            timeout=self._fallback_timeout,
        )
        return CypherQuery(
            statement=statement,
            parameters=parameters,
            timeout=self.default_timeout,
            fallback=fallback,
        )

    def match_node(self, entity: LinkedEntity) -> str:
        """Return a MATCH clause for the provided entity."""
        alias = self._alias_for(entity)
        label = self._label_for(entity)
        param_name = f"{alias}_id"
        return f"MATCH ({alias}:{label} {{id: ${param_name}}})"

    def traverse_relation(self, source: str, target: str, rel_type: str | None = None) -> str:
        """Build a relation traversal clause between two aliases."""
        rel = self._sanitize_label(rel_type or self._default_relation)
        return f"MATCH ({source})-[:{rel}*1..2]->({target})"

    def path_query(self, start: str, end: str, max_hops: int | None = None) -> str:
        """Return a shortest-path clause between two aliases."""
        hops = max_hops or 4
        rel = self._sanitize_label(self._default_relation)
        return f"MATCH path = shortestPath(({start})-[:{rel}*..{hops}]->({end}))"

    def build_where_clause(self, constraints: list[QueryConstraint]) -> str:
        """Translate constraints into a Cypher WHERE clause."""
        if not constraints:
            self._where_params = {}
            return ""

        clauses: list[str] = []
        params: dict[str, Any] = {}
        target = self._where_alias or "n0"
        for index, constraint in enumerate(constraints):
            clause = self._constraint_to_clause(target, constraint, index, params)
            if clause:
                clauses.append(clause)
        self._where_params = params
        if not clauses:
            return ""
        return "WHERE " + " AND ".join(clauses)

    @property
    def _fallback_timeout(self) -> float:
        return max(1.0, (self.default_timeout or 0) / 2)

    def _determine_limit(self, plan: QueryPlan) -> int:
        return max(5, min(100, plan.parsed.complexity * 10))

    def _reset_state(self) -> None:
        self._alias_counter = 0
        self._alias_cache.clear()
        self._where_params = {}
        self._where_alias = "n0"

    def _alias_for(self, entity: LinkedEntity) -> str:
        alias = self._alias_cache.get(entity.kg_node_id)
        if alias:
            return alias
        alias = f"n{self._alias_counter}"
        self._alias_counter += 1
        self._alias_cache[entity.kg_node_id] = alias
        return alias

    def _label_for(self, entity: LinkedEntity) -> str:
        label = entity.mention.entity_type or "Entity"
        return self._sanitize_label(label)

    def _sanitize_label(self, label: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]", "_", label).strip("_")
        return cleaned or "Entity"

    def _extract_hops(self, plan: QueryPlan) -> int:
        for step in plan.steps:
            if step.action == "traverse" and isinstance(step.params, dict):
                hops = step.params.get("hops")
                if isinstance(hops, int) and hops > 0:
                    return hops
        return 4

    def _extract_relation(self, plan: QueryPlan) -> str:
        for step in plan.steps:
            if step.action == "traverse" and isinstance(step.params, dict):
                rel_type = step.params.get("relation")
                if isinstance(rel_type, str) and rel_type:
                    return self._sanitize_label(rel_type)
        return self._default_relation

    def _constraint_to_clause(
        self,
        target: str,
        constraint: QueryConstraint,
        index: int,
        params: dict[str, Any],
    ) -> str:
        operator = (constraint.operator or "=").lower()
        field_name = re.sub(r"[^A-Za-z0-9]", "_", constraint.field or "property").strip("_")
        if not field_name:
            return ""
        lhs = f"{target}.{field_name}"
        value = constraint.value
        param_name = f"{target}_{field_name}_{index}"

        if (
            operator in {"between", "range"}
            and isinstance(value, (list, tuple))
            and len(value) >= 2
        ):
            start_param = f"{param_name}_start"
            end_param = f"{param_name}_end"
            params[start_param] = value[0]
            params[end_param] = value[1]
            return f"({lhs} >= ${start_param} AND {lhs} <= ${end_param})"
        if operator in {">", "gt"}:
            params[param_name] = value
            return f"{lhs} > ${param_name}"
        if operator in {">=", "gte"}:
            params[param_name] = value
            return f"{lhs} >= ${param_name}"
        if operator in {"<", "lt"}:
            params[param_name] = value
            return f"{lhs} < ${param_name}"
        if operator in {"<=", "lte"}:
            params[param_name] = value
            return f"{lhs} <= ${param_name}"
        if operator in {"in", "within"}:
            params[param_name] = value
            return f"{lhs} IN ${param_name}"
        if operator in {"contains", "has"}:
            params[param_name] = value
            return f"{lhs} CONTAINS ${param_name}"
        params[param_name] = value
        return f"{lhs} = ${param_name}"
