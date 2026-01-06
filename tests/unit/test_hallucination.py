"""Tests for the HallucinationGuard component."""

from epip.core.hallucination import HallucinationGuard


def test_review_response_returns_payload(hallucination_guard: HallucinationGuard) -> None:
    payload = "Graph nodes: 2"

    reviewed = hallucination_guard.review_response(payload)

    assert reviewed == payload
