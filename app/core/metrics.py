from prometheus_client import (
    Counter,
    Summary,
    Gauge,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST
)

registry = CollectorRegistry()

REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total number of requests",
    ["method", "route", "status"],
    registry=registry
)

REQUEST_DURATION = Summary(
    "gateway_request_duration_seconds",
    "Request duration in seconds",
    ["route"],
    registry=registry
)

ACTIVE_REQUESTS = Gauge(
    "gateway_concurrent_requests",
    "Current number of concurrent requests being handled",
    registry=registry
)

RATE_LIMITED = Counter(
    "gateway_rate_limited_requests_total",
    "Number of requests that were rate-limited",
    ["route"],
    registry=registry
)


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(registry), CONTENT_TYPE_LATEST
