#!/usr/bin/env python3
"""Real-world E2E smoke for SignalForge API.

Runs a realistic flow against a running backend and fails fast on regressions.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass

import httpx

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 30.0


@dataclass
class SmokeState:
    signal_id: int | None = None
    incident_id: int | None = None


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def get(client: httpx.Client, path: str, expected: int = 200, **kwargs):
    resp = client.get(f"{BASE_URL}{path}", **kwargs)
    expect(resp.status_code == expected, f"GET {path} -> {resp.status_code} != {expected}; body={resp.text[:500]}")
    return resp


def post(client: httpx.Client, path: str, expected: int = 200, **kwargs):
    resp = client.post(f"{BASE_URL}{path}", **kwargs)
    expect(resp.status_code == expected, f"POST {path} -> {resp.status_code} != {expected}; body={resp.text[:500]}")
    return resp


def main() -> int:
    state = SmokeState()
    with httpx.Client(timeout=TIMEOUT) as client:
        # 1) Health
        health = get(client, "/api/health").json()
        expect(health.get("status") == "healthy", "health status is not healthy")

        # 2) Seed realistic data
        ingest = post(client, "/api/signals/ingest?count=40").json()
        expect(ingest.get("status") == "success", "ingest did not return success")
        expect(int(ingest.get("ingested", 0)) > 0, "ingest produced zero signals")

        # 3) List and filter signals
        signals_page = get(client, "/api/signals?page=1&page_size=20").json()
        signals = signals_page.get("signals", [])
        expect(len(signals) > 0, "no signals returned after ingestion")
        state.signal_id = int(signals[0]["id"])

        _ = get(client, "/api/signals?risk_tier=critical&page=1&page_size=10").json()
        _ = get(client, "/api/signals?source=reddit&page=1&page_size=10").json()

        # 4) Signal detail + explainability
        detail = get(client, f"/api/signals/{state.signal_id}").json()
        expect(int(detail["id"]) == state.signal_id, "signal detail id mismatch")

        explain = get(client, f"/api/signals/{state.signal_id}/explain").json()
        expect("risk_explanation" in explain, "missing risk explanation")

        # 5) Dashboard + anomaly + brief + forecast + chat
        overview = get(client, "/api/dashboard/overview").json()
        expect("total_signals" in overview, "dashboard overview missing total_signals")

        _ = get(client, "/api/risk/overview").json()
        _ = get(client, "/api/risk/heatmap").json()
        _ = get(client, "/api/dashboard/risk-trend?hours=24").json()
        _ = get(client, "/api/dashboard/sentiment-drift?hours=24").json()
        _ = get(client, "/api/dashboard/incident-frequency?days=7").json()
        _ = get(client, "/api/dashboard/timeline?limit=20").json()
        _ = get(client, "/api/anomaly/status").json()
        _ = get(client, "/api/anomaly/recent").json()

        brief = get(client, "/api/brief/generate?tone=executive_concise&lookback_hours=24").json()
        expect("situation_overview" in brief, "brief endpoint missing situation_overview")

        _ = get(client, "/api/forecast?metric_name=mrr&horizon=8&lookback_hours=168").json()
        _ = get(client, "/api/forecast/metrics?lookback_hours=168").json()

        chat = post(client, "/api/chat", json={"query": "Summarize top risks from the last 24 hours"}).json()
        expect("answer" in chat, "chat endpoint missing answer")

        # 6) Correlation graph
        _ = get(client, f"/api/correlation/{state.signal_id}").json()
        graph = get(client, f"/api/correlation/graph/{state.signal_id}?depth=2").json()
        expect("nodes" in graph and "edges" in graph, "correlation graph payload invalid")

        # 7) Incident lifecycle
        incident = post(
            client,
            "/api/incidents",
            expected=201,
            json={
                "title": "Smoke test incident",
                "description": "Synthetic incident to validate transitions",
                "severity": "high",
                "source": "system",
                "start_time": "2026-02-27T00:00:00Z",
            },
        ).json()
        state.incident_id = int(incident["id"])

        incidents = get(client, "/api/incidents").json()
        expect(any(int(i["id"]) == state.incident_id for i in incidents), "created incident not listed")

        _ = post(client, f"/api/incidents/{state.incident_id}/acknowledge").json()
        _ = post(client, f"/api/incidents/{state.incident_id}/resolve").json()
        _ = post(client, f"/api/incidents/{state.incident_id}/reopen").json()
        _ = post(client, f"/api/incidents/{state.incident_id}/dismiss").json()

        # 8) Negative test sanity
        bad = client.get(f"{BASE_URL}/api/signals/999999999")
        expect(bad.status_code == 404, f"expected 404 for nonexistent signal, got {bad.status_code}")

    print(json.dumps({"ok": True, "message": "SignalForge real-world smoke passed"}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)
