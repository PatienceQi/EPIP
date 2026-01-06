"""Implementation of the ReAct reasoning agent."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

import structlog

from epip.config import ReActSettings
from epip.core.kg_builder import KnowledgeGraphBuilder
from epip.core.llm_backend import LLMBackend
from epip.reasoning.aggregator import RankedResult, ResultAggregator
from epip.reasoning.decomposer import DecomposedQuery, QueryDecomposer

logger = structlog.get_logger(__name__)


class ActionType(str, Enum):
    """Supported actions in the ReAct loop."""

    SEARCH = "search"
    TRAVERSE = "traverse"
    AGGREGATE = "aggregate"
    CONCLUDE = "conclude"


@dataclass(slots=True)
class Thought:
    """Reasoning thought containing the action to execute next."""

    step: int
    reasoning: str
    action: ActionType
    action_input: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Observation:
    """Observation produced after executing an action."""

    step: int
    result: dict[str, Any]
    success: bool
    error: str | None = None


@dataclass(slots=True)
class ReActTrace:
    """Full trace of the ReAct loop for transparency."""

    query: str
    thoughts: list[Thought]
    observations: list[Observation]
    final_answer: str
    confidence: float
    total_steps: int


class ReActAgent:
    """Multi-step reasoning agent implementing Reason-Act-Observe."""

    def __init__(
        self,
        *,
        kg_builder: KnowledgeGraphBuilder,
        llm_backend: LLMBackend,
        decomposer: QueryDecomposer | None = None,
        aggregator: ResultAggregator | None = None,
        settings: ReActSettings | None = None,
    ) -> None:
        self._kg_builder = kg_builder
        self._llm_backend = llm_backend
        self._decomposer = decomposer or QueryDecomposer()
        self._aggregator = aggregator or ResultAggregator()
        self._settings = settings or ReActSettings()
        self._max_iterations = max(1, self._settings.max_iterations)
        self._timeout = max(0.1, self._settings.timeout_per_step)
        self._plan_hint: str = ""
        self._current_decomposition: DecomposedQuery | None = None
        self._session_results: list[dict[str, Any]] | None = None

    async def reason(self, query: str) -> ReActTrace:
        """Execute the ReAct loop until a conclusion is reached."""
        normalized = query.strip()
        if not normalized:
            raise ValueError("Query cannot be empty.")

        thoughts: list[Thought] = []
        observations: list[Observation] = []
        history: list[dict[str, Any]] = []
        session_results: list[dict[str, Any]] = []

        try:
            self._current_decomposition = await self._decompose_query(normalized)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to decompose query", error=str(exc))
            self._current_decomposition = None
        self._plan_hint = self._describe_plan(self._current_decomposition)
        self._session_results = session_results

        iterations = 0
        try:
            while iterations < self._max_iterations:
                thought = await self._think(normalized, history)
                thoughts.append(thought)

                observation = await self._act(thought)
                observations.append(observation)

                history.append(
                    {
                        "thought": thought.reasoning,
                        "action": thought.action.value,
                        "action_input": thought.action_input,
                        "observation": observation.result,
                        "success": observation.success,
                        "error": observation.error,
                    }
                )

                if observation.success and observation.result:
                    session_results.append(observation.result)

                iterations += 1
                if self._should_terminate(thought, iterations):
                    break
        finally:
            self._plan_hint = ""
            self._current_decomposition = None
            self._session_results = None

        ranked = self._aggregator.aggregate(session_results)
        final_answer, confidence = self._summarize(normalized, ranked, observations)
        return ReActTrace(
            query=normalized,
            thoughts=thoughts,
            observations=observations,
            final_answer=final_answer,
            confidence=min(max(confidence, 0.0), 1.0),
            total_steps=len(thoughts),
        )

    async def _think(self, query: str, history: list[dict[str, Any]]) -> Thought:
        """Generate a thought using the LLM backend with history as context."""
        prompt = self._build_reasoning_prompt(query, history)
        try:
            response = await asyncio.wait_for(
                self._llm_backend.generate(
                    prompt,
                    max_tokens=600,
                    temperature=0.1,
                ),
                timeout=self._timeout,
            )
            payload = self._parse_thought_payload(response)
        except Exception as exc:
            logger.warning("LLM reasoning failed; using heuristic fallback", error=str(exc))
            payload = self._heuristic_payload(query, history)
        return self._build_thought_from_payload(payload, history)

    async def _act(self, thought: Thought) -> Observation:
        """Execute the action described by the thought."""
        action = thought.action
        step = thought.step
        try:
            if action is ActionType.SEARCH:
                result = await self._execute_search(thought)
            elif action is ActionType.TRAVERSE:
                result = await self._execute_traverse(thought)
            elif action is ActionType.AGGREGATE:
                result = self._execute_aggregate(thought)
            elif action is ActionType.CONCLUDE:
                result = self._execute_conclude(thought)
            else:  # pragma: no cover - guard for future enum extensions
                result = self._execute_conclude(thought)
            return Observation(step=step, result=result, success=True)
        except Exception as exc:
            logger.warning("Action execution failed", action=action.value, error=str(exc))
            return Observation(
                step=step,
                result={},
                success=False,
                error=str(exc),
            )

    def _should_terminate(self, thought: Thought, iterations: int) -> bool:
        """Determine whether the loop should terminate."""
        if thought.action is ActionType.CONCLUDE:
            return True
        return iterations >= self._max_iterations

    async def _decompose_query(self, query: str) -> DecomposedQuery | None:
        try:
            return await self._decomposer.decompose(query)
        except Exception:
            return None

    def _describe_plan(self, decomposition: DecomposedQuery | None) -> str:
        if not decomposition:
            return ""
        layers = []
        for layer in decomposition.execution_order:
            humanized = ", ".join(layer)
            layers.append(f"[{humanized}]")
        return " -> ".join(layers)

    def _build_reasoning_prompt(self, query: str, history: list[dict[str, Any]]) -> str:
        history_lines = []
        for index, entry in enumerate(history, start=1):
            observation = entry.get("observation") or {}
            content = observation.get("content") if isinstance(observation, dict) else observation
            history_lines.append(
                f"Step {index} Thought: {entry.get('thought', '')}\n"
                f"Action: {entry.get('action', '')}\n"
                f"Observation: {content}\n"
            )
        history_text = "\n".join(history_lines) if history_lines else "No previous steps."
        plan_hint = f"Planned execution layers: {self._plan_hint}\n" if self._plan_hint else ""
        return (
            "You are coordinating a ReAct (Reason+Act) agent for a policy knowledge graph.\n"
            f"Original query: {query}\n"
            f"{plan_hint}"
            "Pick the next best action among search, traverse, aggregate, and conclude. "
            "Respond strictly with JSON using keys reasoning, action, and action_input.\n"
            f"History:\n{history_text}\n"
            "Next step:"
        )

    def _parse_thought_payload(self, response: str) -> dict[str, Any]:
        candidate = response.strip()
        if not candidate:
            raise ValueError("Empty LLM response.")
        if candidate.startswith("```"):
            candidate = candidate.strip("`")
            candidate = candidate.replace("json", "", 1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start == -1 or end == -1:
                raise
            return json.loads(candidate[start : end + 1])

    def _build_thought_from_payload(
        self,
        payload: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> Thought:
        reasoning = str(payload.get("reasoning") or payload.get("thought") or "").strip()
        action_label = str(payload.get("action") or "").strip().lower() or "conclude"
        action_input = payload.get("action_input") or {}
        if not isinstance(action_input, dict):
            action_input = {}
        try:
            action = ActionType(action_label)
        except ValueError:
            action = ActionType.CONCLUDE
        if not reasoning:
            reasoning = f"Selecting {action.value} due to missing reasoning."
        action_input.setdefault("confidence", 0.5)
        action_input.setdefault("path_length", 1)
        return Thought(
            step=len(history) + 1,
            reasoning=reasoning,
            action=action,
            action_input=action_input,
        )

    def _heuristic_payload(
        self,
        query: str,
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not history:
            return {
                "reasoning": "Start by searching for the entities mentioned in the query.",
                "action": ActionType.SEARCH.value,
                "action_input": {"question": query},
            }
        last_observation = history[-1].get("observation") or {}
        if isinstance(last_observation, dict) and last_observation.get("content"):
            return {
                "reasoning": "Use gathered evidence to conclude.",
                "action": ActionType.CONCLUDE.value,
                "action_input": {"confidence": 0.6},
            }
        return {
            "reasoning": "Aggregate collected context to summarize progress.",
            "action": ActionType.AGGREGATE.value,
            "action_input": {},
        }

    async def _execute_search(self, thought: Thought) -> dict[str, Any]:
        question = self._resolve_question(thought.action_input)
        mode = thought.action_input.get("mode", "mix")
        response = await asyncio.wait_for(
            self._kg_builder.query(question, mode=mode),
            timeout=self._timeout,
        )
        return {
            "content": response,
            "confidence": thought.action_input.get("confidence", 0.5),
            "path_length": thought.action_input.get("path_length", 1),
            "source_queries": [question],
            "mode": mode,
        }

    async def _execute_traverse(self, thought: Thought) -> dict[str, Any]:
        question = self._resolve_question(thought.action_input)
        mode = thought.action_input.get("mode", "path")
        response = await asyncio.wait_for(
            self._kg_builder.query(question, mode=mode),
            timeout=self._timeout,
        )
        return {
            "content": response,
            "confidence": min(1.0, thought.action_input.get("confidence", 0.6)),
            "path_length": max(1, thought.action_input.get("path_length", 2)),
            "source_queries": [question],
            "mode": mode,
        }

    def _execute_aggregate(self, thought: Thought) -> dict[str, Any]:
        results = thought.action_input.get("results")
        if results is None:
            results = list(self._session_results or [])
        ranked = self._aggregator.aggregate(
            results,
            strategy=thought.action_input.get("strategy", "confidence"),
        )
        if not ranked:
            return {
                "content": "No intermediate findings to aggregate.",
                "confidence": 0.0,
                "path_length": 0,
                "source_queries": [],
            }
        summary = "; ".join(result.content for result in ranked[:3])
        flattened_sources: list[str] = []
        for item in ranked:
            for source in item.source_queries:
                if source not in flattened_sources:
                    flattened_sources.append(source)
        return {
            "content": summary,
            "confidence": ranked[0].confidence,
            "path_length": ranked[0].path_length,
            "source_queries": flattened_sources,
            "ranked": [asdict(item) for item in ranked],
        }

    def _execute_conclude(self, thought: Thought) -> dict[str, Any]:
        return {
            "content": thought.reasoning,
            "confidence": thought.action_input.get("confidence", 0.7),
            "path_length": thought.action_input.get("path_length", 0),
            "source_queries": thought.action_input.get("source_queries", []),
        }

    def _resolve_question(self, action_input: dict[str, Any]) -> str:
        question = (
            action_input.get("question")
            or action_input.get("sub_query")
            or action_input.get("prompt")
        )
        if question:
            return str(question)
        if self._current_decomposition and self._current_decomposition.sub_queries:
            return self._current_decomposition.sub_queries[0].question
        raise ValueError("Action input must include a question or sub_query.")

    def _summarize(
        self,
        query: str,
        ranked_results: list[RankedResult],
        observations: list[Observation],
    ) -> tuple[str, float]:
        if ranked_results:
            snippets = "; ".join(result.content for result in ranked_results[:3])
            return snippets, ranked_results[0].confidence
        for observation in reversed(observations):
            content = observation.result.get("content")
            if content:
                return str(content), 0.3
        return f"Unable to resolve answer for: {query}", 0.0
