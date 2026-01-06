"""Asynchronous performance benchmarking harness for EPIP queries."""

from __future__ import annotations

import argparse
import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from epip.api.dependencies import get_query_engine, get_settings
from epip.benchmark import BenchmarkResult, LatencyStats, QueryBenchmark
from epip.cache import CacheConfig, QueryCache, QueryFingerprint
from epip.utils.logging import get_logger

QueryFn = Callable[[str], Awaitable[object]]

logger = get_logger()


DEFAULT_QUERY_COUNT = 50
DEFAULT_CONCURRENCY = 5
CONCURRENCY_VALIDATION_USERS = 10
SAMPLE_QUERIES = [
    "Summarize the latest carbon reduction policies.",
    "List incentives for solar adoption in the EU.",
    "Provide ESG risk drivers for automotive suppliers.",
    "Show key policy trends for clean water access.",
]


@dataclass(slots=True)
class ThroughputMetrics:
    """Aggregated throughput information for a benchmark run."""

    total_queries: int
    duration_s: float
    concurrency: int

    @property
    def qps(self) -> float:
        if self.duration_s == 0:
            return float("inf")
        return self.total_queries / self.duration_s


@dataclass(slots=True)
class CacheComparison:
    """Performance comparison between cold and warm cache runs."""

    cold_stats: LatencyStats
    warm_stats: LatencyStats
    cold_duration_s: float
    warm_duration_s: float
    hit_rate: float

    @property
    def improvement_factor(self) -> float:
        if self.warm_duration_s == 0:
            return float("inf")
        return self.cold_duration_s / self.warm_duration_s


@dataclass(slots=True)
class PerformanceMetrics:
    """High-level snapshot of benchmarked performance characteristics."""

    latency: LatencyStats
    throughput: ThroughputMetrics
    concurrency_level: int
    concurrency_stats: LatencyStats
    cache: CacheComparison


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be a positive integer.")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the benchmarking harness."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queries",
        type=_positive_int,
        default=DEFAULT_QUERY_COUNT,
        help="Total number of synthetic queries to issue during the benchmark.",
    )
    parser.add_argument(
        "--concurrency",
        type=_positive_int,
        default=DEFAULT_CONCURRENCY,
        help="Maximum number of concurrent requests for the latency/throughput test.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("performance_report.md"),
        help="Destination file where the Markdown report will be written.",
    )
    return parser.parse_args(argv)


def _generate_queries(total: int, *, unique: bool) -> list[str]:
    """Create a synthetic workload of benchmark queries."""

    queries: list[str] = []
    for idx in range(total):
        template = SAMPLE_QUERIES[idx % len(SAMPLE_QUERIES)]
        if unique:
            queries.append(f"{template} #{idx}")
        else:
            queries.append(template)
    return queries


async def _execute_workload(
    query_fn: QueryFn,
    queries: Sequence[str],
    *,
    concurrency: int,
    cache: QueryCache | None = None,
    fingerprint: QueryFingerprint | None = None,
) -> tuple[LatencyStats, list[BenchmarkResult], float]:
    """Run the provided workload and return stats, raw samples, and duration."""

    benchmark = QueryBenchmark(query_fn, cache=cache, fingerprint=fingerprint)
    start = time.perf_counter()
    results = await benchmark.run(list(queries), concurrency=concurrency)
    duration = time.perf_counter() - start
    stats = benchmark.compute_stats(results)
    return stats, results, duration


async def execute_performance_suite(
    *,
    total_queries: int,
    concurrency: int,
    query_fn: QueryFn | None = None,
    cache_config: CacheConfig | None = None,
) -> PerformanceMetrics:
    """Collect latency, throughput, concurrency, and cache metrics."""

    if query_fn is None:
        engine = get_query_engine()
        query_fn = engine.query
    if cache_config is None:
        cache_config = CacheConfig()

    workload = _generate_queries(total_queries, unique=True)
    latency_stats, _, latency_duration = await _execute_workload(
        query_fn,
        workload,
        concurrency=concurrency,
    )
    throughput = ThroughputMetrics(
        total_queries=len(workload),
        duration_s=latency_duration,
        concurrency=concurrency,
    )

    concurrent_workload = _generate_queries(
        max(total_queries, CONCURRENCY_VALIDATION_USERS),
        unique=True,
    )
    concurrency_stats, _, _ = await _execute_workload(
        query_fn,
        concurrent_workload,
        concurrency=CONCURRENCY_VALIDATION_USERS,
    )

    cache_workload = _generate_queries(total_queries, unique=False)
    cold_stats, _, cold_duration = await _execute_workload(
        query_fn,
        cache_workload,
        concurrency=concurrency,
    )

    cache = QueryCache(cache_config)
    fingerprint = QueryFingerprint()
    # Prime cache to ensure subsequent run experiences hits.
    await _execute_workload(
        query_fn,
        cache_workload,
        concurrency=concurrency,
        cache=cache,
        fingerprint=fingerprint,
    )
    warm_stats, warm_results, warm_duration = await _execute_workload(
        query_fn,
        cache_workload,
        concurrency=concurrency,
        cache=cache,
        fingerprint=fingerprint,
    )
    hits = sum(1 for sample in warm_results if sample.cached)
    hit_rate = (hits / len(warm_results)) if warm_results else 0.0
    await cache.close()

    cache_metrics = CacheComparison(
        cold_stats=cold_stats,
        warm_stats=warm_stats,
        cold_duration_s=cold_duration,
        warm_duration_s=warm_duration,
        hit_rate=hit_rate,
    )
    return PerformanceMetrics(
        latency=latency_stats,
        throughput=throughput,
        concurrency_level=CONCURRENCY_VALIDATION_USERS,
        concurrency_stats=concurrency_stats,
        cache=cache_metrics,
    )


def build_markdown_report(metrics: PerformanceMetrics) -> str:
    """Render collected metrics into a Markdown report suitable for sharing."""

    throughput = metrics.throughput
    cache = metrics.cache
    lines = ["# EPIP Performance Benchmark", ""]
    lines.extend([
        "## Latency",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Total Queries | {throughput.total_queries} |",
        f"| p50 (ms) | {metrics.latency.p50:.2f} |",
        f"| p95 (ms) | {metrics.latency.p95:.2f} |",
        f"| p99 (ms) | {metrics.latency.p99:.2f} |",
        f"| Mean (ms) | {metrics.latency.mean:.2f} |",
        f"| Min (ms) | {metrics.latency.min:.2f} |",
        f"| Max (ms) | {metrics.latency.max:.2f} |",
    ])

    lines.extend([
        "",
        "## Throughput",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Concurrency | {throughput.concurrency} |",
        f"| Duration (s) | {throughput.duration_s:.2f} |",
        f"| Queries per Second | {throughput.qps:.2f} |",
    ])

    lines.extend([
        "",
        "## Concurrent Queries",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Users | {metrics.concurrency_level} |",
        f"| p95 (ms) | {metrics.concurrency_stats.p95:.2f} |",
        f"| p99 (ms) | {metrics.concurrency_stats.p99:.2f} |",
    ])

    lines.extend([
        "",
        "## Cache Performance",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Cold p95 (ms) | {cache.cold_stats.p95:.2f} |",
        f"| Warm p95 (ms) | {cache.warm_stats.p95:.2f} |",
        f"| Cold Duration (s) | {cache.cold_duration_s:.2f} |",
        f"| Warm Duration (s) | {cache.warm_duration_s:.2f} |",
        f"| Cache Hit Rate | {cache.hit_rate:.2%} |",
        f"| Improvement Factor | {cache.improvement_factor:.2f}x |",
    ])
    return "\n".join(lines)


def _resolve_cache_config() -> CacheConfig:
    settings = get_settings()
    redis_url = getattr(settings, "redis_url", CacheConfig().redis_url)
    return CacheConfig(redis_url=redis_url)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    logger.info(
        "starting_performance_benchmark",
        queries=args.queries,
        concurrency=args.concurrency,
        output=str(args.output),
    )
    metrics = asyncio.run(
        execute_performance_suite(
            total_queries=args.queries,
            concurrency=args.concurrency,
            cache_config=_resolve_cache_config(),
        )
    )
    report = build_markdown_report(metrics)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)
    logger.info(
        "performance_benchmark_complete",
        qps=f"{metrics.throughput.qps:.2f}",
        cache_improvement=f"{metrics.cache.improvement_factor:.2f}",
    )


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
