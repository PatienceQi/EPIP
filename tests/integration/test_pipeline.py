"""Integration tests for the lightweight orchestration pipeline."""

import pytest

from epip.core.query_engine import QueryEngine


@pytest.mark.asyncio
async def test_pipeline_processes_query_end_to_end(query_engine: QueryEngine) -> None:
    result = await query_engine.query("Provide insights")

    assert result == "mocked-query-result"


@pytest.mark.asyncio
async def test_pipeline_is_deterministic(query_engine: QueryEngine) -> None:
    first = await query_engine.query("Provide insights")
    second = await query_engine.query("Provide insights")

    assert first == second
