from backend.observability.metrics import InMemoryMetrics


def test_metrics_snapshot_includes_latency_percentiles_and_counts():
    m = InMemoryMetrics(latency_window=10)

    m.observe_request("/api/health", 200, 12.0)
    m.observe_request("/api/health", 200, 24.0)
    m.observe_request("/api/signals", 500, 200.0)

    snap = m.snapshot()

    assert snap["requests_total"] == 3
    assert snap["status_counts"]["2xx"] == 2
    assert snap["status_counts"]["5xx"] == 1
    assert snap["path_counts"]["/api/health"] == 2
    assert snap["latency_ms"]["samples"] == 3
    assert snap["latency_ms"]["p95"] >= snap["latency_ms"]["p50"]
