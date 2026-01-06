"""Command-line entrypoint for running query latency benchmarks."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

import click

from epip.api.dependencies import get_query_engine, get_settings
from epip.benchmark import QueryBenchmark
from epip.cache import CacheConfig, QueryCache, QueryFingerprint
from epip.utils.logging import get_logger

logger = get_logger()


def _load_queries(path: Path | None, inline_queries: Sequence[str]) -> list[str]:
    queries = [query.strip() for query in inline_queries if query.strip()]
    if path is not None:
        content = path.read_text(encoding="utf-8")
        queries.extend(line.strip() for line in content.splitlines() if line.strip())
    deduplicated = []
    for query in queries:
        if query not in deduplicated:
            deduplicated.append(query)
    return deduplicated


async def _execute_benchmark(
    queries: list[str],
    concurrency: int,
    use_cache: bool,
) -> tuple[str, QueryCache | None]:
    settings = get_settings()
    engine = get_query_engine()
    cache: QueryCache | None = None
    fingerprint: QueryFingerprint | None = None
    if use_cache:
        cache = QueryCache(CacheConfig(redis_url=settings.redis_url))
        fingerprint = QueryFingerprint()

    benchmark = QueryBenchmark(engine.query, cache=cache, fingerprint=fingerprint)
    results = await benchmark.run(queries, concurrency=concurrency)
    return benchmark.report(results), cache


@click.command()
@click.option("--query", "queries", multiple=True, help="Query to benchmark; pass multiple times.")
@click.option(
    "--file",
    "query_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a file with one query per line.",
)
@click.option(
    "--concurrency",
    type=click.IntRange(1, 32),
    default=1,
    show_default=True,
    help="Number of concurrent requests to issue.",
)
@click.option(
    "--use-cache/--no-cache",
    default=True,
    show_default=True,
    help="Toggle whether the benchmark should leverage the query cache.",
)
def main(
    queries: Sequence[str],
    query_file: Path | None,
    concurrency: int,
    use_cache: bool,
) -> None:
    """Measure query latency with optional cache integration."""
    selected_queries = _load_queries(query_file, queries)
    if not selected_queries:
        raise click.ClickException("Provide at least one query via --query or --file.")

    logger.info("running_query_benchmark", total=len(selected_queries), concurrency=concurrency)
    report, cache = asyncio.run(_execute_benchmark(selected_queries, concurrency, use_cache))
    click.echo(report)

    if cache is not None:
        stats = asyncio.run(cache.stats())
        click.echo(
            f"\nCache hits: {stats.hits}, misses: {stats.misses}, hit rate: {stats.hit_rate:.2%}"
        )
        asyncio.run(cache.close())


if __name__ == "__main__":  # pragma: no cover - CLI hook
    main()
