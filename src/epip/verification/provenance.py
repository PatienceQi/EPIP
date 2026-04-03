"""Provenance utilities that map conclusions back to their supporting nodes."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

import structlog

from epip.verification.trace import ReasoningTrace

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class ProvenanceInfo:
    """Container describing how a conclusion was produced."""

    conclusion: str
    source_nodes: list[str]
    reasoning_chain: list[str]
    confidence: float
    evidence_count: int


class ProvenanceService:
    """Builds provenance data for reasoning traces."""

    def __init__(self, kg_client: Any | None = None) -> None:
        self._kg_client = kg_client

    async def trace_back(self, conclusion_node_id: str, trace: ReasoningTrace) -> ProvenanceInfo:
        """Return provenance information for ``conclusion_node_id``."""

        if not trace.nodes:
            raise ValueError("Trace does not contain any nodes.")

        node_map = {node.node_id: node for node in trace.nodes}
        if conclusion_node_id not in node_map:
            raise ValueError(f"Unknown conclusion node '{conclusion_node_id}'.")

        chain = self.build_reasoning_chain(trace, conclusion_node_id)
        if not chain:
            chain = [conclusion_node_id]

        conclusion_node = node_map[conclusion_node_id]
        sources = [node_id for node_id in chain if node_id != conclusion_node_id]
        confidence = (
            sum(node_map[node_id].confidence for node_id in chain) / len(chain)
            if chain
            else conclusion_node.confidence
        )
        evidence_count = sum(1 for node_id in chain if node_map[node_id].node_type == "observation")

        # Fetch KG context opportunistically to warm caches; ignored if unavailable.
        try:
            await self.get_kg_context([conclusion_node_id, *sources])
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("Failed to retrieve KG context", error=str(exc))

        return ProvenanceInfo(
            conclusion=conclusion_node.content,
            source_nodes=sources,
            reasoning_chain=chain,
            confidence=max(0.0, min(1.0, confidence)),
            evidence_count=evidence_count,
        )

    async def get_kg_context(self, node_ids: list[str]) -> dict[str, Any]:
        """Return knowledge-graph metadata for ``node_ids`` when a client is configured."""

        if not node_ids or not self._kg_client:
            return {}

        method = self._resolve_kg_method()
        if not method:
            return {}

        context: dict[str, Any] = {}
        for node_id in node_ids:
            try:
                result = method(node_id)
                if inspect.isawaitable(result):
                    result = await result
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("KG context fetch failed", node_id=node_id, error=str(exc))
                continue
            if result is not None:
                context[node_id] = result
        return context

    def build_reasoning_chain(self, trace: ReasoningTrace, target_node: str) -> list[str]:
        """Build the ordered chain of nodes leading to ``target_node``."""

        node_map = {node.node_id: node for node in trace.nodes}
        if target_node not in node_map:
            return []

        incoming: dict[str, list[tuple[float, str]]] = {node.node_id: [] for node in trace.nodes}
        for edge in trace.edges:
            if edge.target_id in incoming and edge.source_id in node_map:
                incoming[edge.target_id].append((edge.weight, edge.source_id))

        chain: list[str] = []
        visited: set[str] = set()
        cursor = target_node
        while cursor and cursor not in visited:
            chain.append(cursor)
            visited.add(cursor)
            candidates = incoming.get(cursor, [])
            if not candidates:
                break
            sorted_candidates = sorted(candidates, key=lambda item: item[0], reverse=True)
            next_source = None
            for _, candidate_source in sorted_candidates:
                if candidate_source not in visited:
                    next_source = candidate_source
                    break
            if not next_source:
                break
            cursor = next_source
        return list(reversed(chain))

    def _resolve_kg_method(self) -> Any:
        for attr in ("get_context", "get_node", "fetch_node", "fetch"):
            candidate = getattr(self._kg_client, attr, None)
            if callable(candidate):
                return candidate
        return None
