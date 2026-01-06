"""Observability primitives built on top of ``prometheus_client``.

This module wraps the Prometheus Python client so that callers always have a
collector API, even when the optional dependency is missing in local
environments. When ``prometheus_client`` cannot be imported, a lightweight
in-memory shim is used that mimics the small subset of the interface EPIP
requires for its monitoring story.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

try:  # pragma: no cover - exercised indirectly through integration paths
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
except Exception:  # pragma: no cover - fallback only used when dependency is missing
    class CollectorRegistry:  # type: ignore[no-redef]
        """Minimal CollectorRegistry compatible with the Prometheus client API."""

        def __init__(self) -> None:
            self._metrics: list[_BaseMetric] = []

        def register(self, metric: _BaseMetric) -> None:
            self._metrics.append(metric)

        def collect(self) -> list[_BaseMetric]:
            return list(self._metrics)

    class _MetricHandle:
        def __init__(self, metric: _BaseMetric, label_values: tuple[str, ...]) -> None:
            self._metric = metric
            self._labels = label_values

        def inc(self, amount: float = 1.0) -> None:
            self._metric._inc(self._labels, amount)

        def observe(self, value: float) -> None:
            self._metric._observe(self._labels, value)

        def set(self, value: float) -> None:
            self._metric._set(self._labels, value)

    class _BaseMetric:
        metric_type = "metric"

        def __init__(
            self,
            name: str,
            documentation: str,
            labelnames: Sequence[str] | None = None,
            registry: CollectorRegistry | None = None,
        ) -> None:
            self.name = name
            self.documentation = documentation
            self.labelnames: tuple[str, ...] = tuple(labelnames or ())
            self._samples: dict[tuple[str, ...], float] = {}
            if registry is not None:
                registry.register(self)

        def labels(self, *args: str, **kwargs: str) -> _MetricHandle:
            if kwargs:
                values = tuple(kwargs[name] for name in self.labelnames)
            else:
                values = tuple(args)
            if len(values) != len(self.labelnames):
                raise ValueError("Label cardinality mismatch")
            return _MetricHandle(self, values)

        def samples(self) -> Iterable[tuple[tuple[str, ...], float]]:
            for labels in sorted(self._samples):
                yield labels, self._samples[labels]

        def _inc(self, labels: tuple[str, ...], amount: float) -> None:
            raise NotImplementedError

        def _observe(self, labels: tuple[str, ...], value: float) -> None:
            raise NotImplementedError

        def _set(self, labels: tuple[str, ...], value: float) -> None:
            raise NotImplementedError

    class Counter(_BaseMetric):  # type: ignore[no-redef]
        metric_type = "counter"

        def _inc(self, labels: tuple[str, ...], amount: float) -> None:
            self._samples[labels] = self._samples.get(labels, 0.0) + amount

        def _observe(self, labels: tuple[str, ...], value: float) -> None:
            self._inc(labels, value)

        def _set(self, labels: tuple[str, ...], value: float) -> None:
            self._samples[labels] = value

    class Gauge(_BaseMetric):  # type: ignore[no-redef]
        metric_type = "gauge"

        def _inc(self, labels: tuple[str, ...], amount: float) -> None:
            self._samples[labels] = self._samples.get(labels, 0.0) + amount

        def _observe(self, labels: tuple[str, ...], value: float) -> None:
            self._set(labels, value)

        def _set(self, labels: tuple[str, ...], value: float) -> None:
            self._samples[labels] = value

    class Histogram(_BaseMetric):  # type: ignore[no-redef]
        metric_type = "histogram"

        def _observe(self, labels: tuple[str, ...], value: float) -> None:
            history = self._samples.setdefault(labels, 0.0)
            self._samples[labels] = history + value

        def _inc(self, labels: tuple[str, ...], amount: float) -> None:
            self._observe(labels, amount)

        def _set(self, labels: tuple[str, ...], value: float) -> None:
            self._samples[labels] = value

    def generate_latest(registry: CollectorRegistry) -> bytes:  # type: ignore[no-redef]
        lines: list[str] = []
        for metric in sorted(registry.collect(), key=lambda item: item.name):
            lines.append(f"# HELP {metric.name} {metric.documentation}")
            lines.append(f"# TYPE {metric.name} {metric.metric_type}")
            for labels, value in metric.samples():
                label_str = ""
                if labels:
                    encoded = ",".join(
                        f'{name}="{label}"'
                        for name, label in zip(metric.labelnames, labels, strict=False)
                    )
                    label_str = f"{{{encoded}}}"
                lines.append(f"{metric.name}{label_str} {value}")
        return "\n".join(lines).encode("utf-8")

DEFAULT_DOCS = {
    "epip_requests_total": "Total number of EPIP API requests",
    "epip_request_duration_seconds": "Latency of EPIP API requests",
    "epip_queries_total": "Knowledge discovery queries per tenant",
    "epip_cache_hit_ratio": "Ratio of cache hits for each tenant",
    "epip_kg_nodes_total": "Knowledge graph nodes per tenant",
}


def _build_metrics(registry: CollectorRegistry):
    request_count = Counter(
        "epip_requests_total",
        DEFAULT_DOCS["epip_requests_total"],
        labelnames=("method", "endpoint", "status"),
        registry=registry,
    )
    request_latency = Histogram(
        "epip_request_duration_seconds",
        DEFAULT_DOCS["epip_request_duration_seconds"],
        labelnames=("method", "endpoint"),
        registry=registry,
    )
    query_count = Counter(
        "epip_queries_total",
        DEFAULT_DOCS["epip_queries_total"],
        labelnames=("tenant_id", "query_type"),
        registry=registry,
    )
    cache_hit_ratio = Gauge(
        "epip_cache_hit_ratio",
        DEFAULT_DOCS["epip_cache_hit_ratio"],
        labelnames=("tenant_id",),
        registry=registry,
    )
    kg_nodes = Gauge(
        "epip_kg_nodes_total",
        DEFAULT_DOCS["epip_kg_nodes_total"],
        labelnames=("tenant_id",),
        registry=registry,
    )
    return request_count, request_latency, query_count, cache_hit_ratio, kg_nodes


DEFAULT_REGISTRY = CollectorRegistry()
(REQUEST_COUNT, REQUEST_LATENCY, QUERY_COUNT, CACHE_HIT_RATIO, KG_NODES) = _build_metrics(
    DEFAULT_REGISTRY
)


class MetricsCollector:
    """Helper that records key service metrics and exposes them in text form."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or DEFAULT_REGISTRY
        if registry is None:
            self.request_count = REQUEST_COUNT
            self.request_latency = REQUEST_LATENCY
            self.query_count = QUERY_COUNT
            self.cache_hit_ratio = CACHE_HIT_RATIO
            self.kg_nodes = KG_NODES
        else:
            (
                self.request_count,
                self.request_latency,
                self.query_count,
                self.cache_hit_ratio,
                self.kg_nodes,
            ) = _build_metrics(self.registry)

    def record_request(
        self, method: str, endpoint: str, status: str | int, duration: float
    ) -> None:
        labels = {"method": method.upper(), "endpoint": endpoint}
        self.request_count.labels(status=str(status), **labels).inc()
        self.request_latency.labels(**labels).observe(float(duration))

    def record_query(self, tenant_id: str, query_type: str) -> None:
        self.query_count.labels(tenant_id=tenant_id, query_type=query_type).inc()

    def update_cache_ratio(self, tenant_id: str, ratio: float) -> None:
        self.cache_hit_ratio.labels(tenant_id=tenant_id).set(float(ratio))

    def update_kg_nodes(self, tenant_id: str, count: int | float) -> None:
        self.kg_nodes.labels(tenant_id=tenant_id).set(float(count))

    def get_metrics(self) -> str:
        """Return the current metrics snapshot in the Prometheus text format."""
        payload = generate_latest(self.registry)
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        return str(payload)


metrics_collector = MetricsCollector()


__all__ = [
    "MetricsCollector",
    "CollectorRegistry",
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "QUERY_COUNT",
    "CACHE_HIT_RATIO",
    "KG_NODES",
    "metrics_collector",
]
