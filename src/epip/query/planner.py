"""Query planning utilities that orchestrate structured query execution."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import structlog

from epip.query.linker import LinkedEntity
from epip.query.parser import EntityMention, ParsedQuery, QueryConstraint, QueryIntent

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class QueryStep:
    """Single query execution step."""

    step_id: int
    action: str
    params: dict[str, Any]
    depends_on: list[int] = field(default_factory=list)


@dataclass(slots=True)
class QueryPlan:
    """Structured plan describing the execution strategy."""

    query_id: str
    parsed: ParsedQuery
    linked_entities: list[LinkedEntity]
    steps: list[QueryStep]
    estimated_cost: float


class QueryPlanner:
    """Generate and validate executable query plans."""

    def __init__(self, *, id_factory: Callable[[], str] | None = None) -> None:
        self._id_factory = id_factory or (lambda: uuid4().hex)

    async def plan(self, parsed: ParsedQuery, linked: list[LinkedEntity]) -> QueryPlan:
        """Transform a parsed query into a multi-step execution plan."""
        query_id = self._id_factory()
        steps = self._build_steps(parsed, linked)
        estimated_cost = self._estimate_cost(parsed, steps)
        plan = QueryPlan(
            query_id=query_id,
            parsed=parsed,
            linked_entities=linked,
            steps=steps,
            estimated_cost=estimated_cost,
        )
        errors = self.validate_plan(plan)
        if errors:
            logger.warning("Generated query plan has validation issues", errors=errors)
        return plan

    def validate_plan(self, plan: QueryPlan) -> list[str]:
        """Perform lightweight validation on a generated plan."""
        errors: list[str] = []
        if not plan.query_id:
            errors.append("query_id is required.")
        if not plan.steps:
            errors.append("plan must contain at least one step.")
        seen_ids: set[int] = set()
        for step in plan.steps:
            if step.step_id in seen_ids:
                errors.append(f"duplicate step id detected: {step.step_id}")
            for dependency in step.depends_on:
                if dependency not in seen_ids:
                    errors.append(f"step {step.step_id} depends on unknown step {dependency}")
                if dependency == step.step_id:
                    errors.append(f"step {step.step_id} cannot depend on itself")
            seen_ids.add(step.step_id)
        if plan.parsed.complexity < 1 or plan.parsed.complexity > 5:
            errors.append("parsed.complexity must be within [1, 5].")
        return errors

    def to_json(self, plan: QueryPlan) -> str:
        """Serialize the plan into a JSON string suitable for tracing."""
        payload = {
            "query_id": plan.query_id,
            "estimated_cost": plan.estimated_cost,
            "parsed": self._serialize_parsed(plan.parsed),
            "linked_entities": [
                {
                    "mention": self._serialize_mention(link.mention),
                    "kg_node_id": link.kg_node_id,
                    "kg_node_name": link.kg_node_name,
                    "confidence": link.confidence,
                    "alternatives": link.alternatives,
                }
                for link in plan.linked_entities
            ],
            "steps": [
                {
                    "step_id": step.step_id,
                    "action": step.action,
                    "params": step.params,
                    "depends_on": step.depends_on,
                }
                for step in plan.steps
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_steps(self, parsed: ParsedQuery, linked: list[LinkedEntity]) -> list[QueryStep]:
        steps: list[QueryStep] = []
        step_id = 1

        current_scope: list[int] = []
        for mention in parsed.entities:
            params = {"text": mention.text}
            linked_entity = self._find_link(linked, mention)
            if linked_entity:
                params["node_id"] = linked_entity.kg_node_id
                params["confidence"] = round(linked_entity.confidence, 3)
            step = QueryStep(step_id=step_id, action="search", params=params, depends_on=[])
            steps.append(step)
            current_scope.append(step_id)
            step_id += 1

        if parsed.intent in (QueryIntent.RELATION, QueryIntent.PATH):
            params = {
                "strategy": (
                    "shortest_path" if parsed.intent == QueryIntent.PATH else "neighbor_lookup"
                ),
                "hops": 2 if parsed.intent == QueryIntent.RELATION else 4,
            }
            step = QueryStep(
                step_id=step_id,
                action="traverse",
                params=params,
                depends_on=current_scope.copy(),
            )
            steps.append(step)
            current_scope = [step_id]
            step_id += 1

        for constraint in parsed.constraints:
            step = QueryStep(
                step_id=step_id,
                action="filter",
                params=self._serialize_constraint(constraint),
                depends_on=current_scope.copy() if current_scope else [],
            )
            steps.append(step)
            current_scope = [step_id]
            step_id += 1

        if parsed.intent in (QueryIntent.AGGREGATE, QueryIntent.COMPARE):
            params = {
                "operation": "compare" if parsed.intent == QueryIntent.COMPARE else "aggregate",
                "metric": "count",
            }
            step = QueryStep(
                step_id=step_id,
                action="aggregate",
                params=params,
                depends_on=current_scope.copy() if current_scope else [],
            )
            steps.append(step)
            current_scope = [step_id]
            step_id += 1

        if not steps:
            steps.append(
                QueryStep(
                    step_id=step_id,
                    action="search",
                    params={"text": parsed.original},
                    depends_on=[],
                )
            )
        return steps

    def _estimate_cost(self, parsed: ParsedQuery, steps: Sequence[QueryStep]) -> float:
        baseline = max(1, parsed.complexity)
        multiplier = 1.0 + (len(steps) * 0.2)
        return round(float(baseline * multiplier), 2)

    @staticmethod
    def _serialize_parsed(parsed: ParsedQuery) -> dict[str, Any]:
        return {
            "original": parsed.original,
            "intent": parsed.intent.value,
            "complexity": parsed.complexity,
            "entities": [QueryPlanner._serialize_mention(mention) for mention in parsed.entities],
            "constraints": [
                QueryPlanner._serialize_constraint(constraint) for constraint in parsed.constraints
            ],
        }

    @staticmethod
    def _serialize_mention(mention: EntityMention) -> dict[str, Any]:
        return {
            "text": mention.text,
            "entity_type": mention.entity_type,
            "start": mention.start,
            "end": mention.end,
        }

    @staticmethod
    def _serialize_constraint(constraint: QueryConstraint) -> dict[str, Any]:
        return {
            "field": constraint.field,
            "operator": constraint.operator,
            "value": constraint.value,
        }

    @staticmethod
    def _find_link(linked: list[LinkedEntity], mention: EntityMention) -> LinkedEntity | None:
        for link in linked:
            if link.mention == mention:
                return link
        return None
