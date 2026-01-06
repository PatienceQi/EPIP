"""Lightweight safeguards for hallucination detection."""


class HallucinationGuard:
    """Represent a placeholder guardrail for generated answers."""

    def review_response(self, response: str) -> str:
        """Return the response untouched while logging potential hooks."""
        # Future implementation: hook into evaluation metrics to score hallucination risk.
        return response
