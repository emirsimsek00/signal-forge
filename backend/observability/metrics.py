"""Lightweight in-process metrics for SignalForge.

This is intentionally dependency-light for easy deploys (no Prometheus client required).
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock


class InMemoryMetrics:
    def __init__(self, latency_window: int = 2000) -> None:
        self._lock = Lock()
        self._requests_total = 0
        self._status_counts: dict[str, int] = defaultdict(int)
        self._path_counts: dict[str, int] = defaultdict(int)
        self._latencies_ms = deque(maxlen=latency_window)

    def observe_request(self, path: str, status_code: int, duration_ms: float) -> None:
        bucket = f"{status_code // 100}xx"
        with self._lock:
            self._requests_total += 1
            self._status_counts[bucket] += 1
            self._path_counts[path] += 1
            self._latencies_ms.append(float(duration_ms))

    def snapshot(self) -> dict:
        with self._lock:
            latencies = list(self._latencies_ms)
            sorted_latencies = sorted(latencies)

            def percentile(p: float) -> float:
                if not sorted_latencies:
                    return 0.0
                idx = int((len(sorted_latencies) - 1) * p)
                return round(sorted_latencies[idx], 2)

            return {
                "requests_total": self._requests_total,
                "status_counts": dict(self._status_counts),
                "path_counts": dict(self._path_counts),
                "latency_ms": {
                    "samples": len(sorted_latencies),
                    "p50": percentile(0.50),
                    "p95": percentile(0.95),
                    "p99": percentile(0.99),
                },
            }


metrics = InMemoryMetrics()
