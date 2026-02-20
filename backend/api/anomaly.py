"""Anomaly detection API — query detected anomalies."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from backend.anomaly.detector import detector

router = APIRouter(prefix="/api/anomaly", tags=["anomaly"])


@router.get("/recent")
async def get_recent_anomalies(limit: int = 20):
    """Get recently detected anomaly events."""
    events = detector.recent_events[:limit]
    return {
        "events": [
            {
                **{k: v for k, v in asdict(evt).items() if k != "detected_at"},
                "detected_at": evt.detected_at.isoformat(),
            }
            for evt in events
        ],
        "total": len(detector.recent_events),
    }


@router.get("/status")
async def get_anomaly_status():
    """Get current anomaly detection status."""
    events = detector.recent_events
    severity_counts = {"critical": 0, "high": 0, "moderate": 0}
    type_counts = {"volume_spike": 0, "risk_spike": 0, "sentiment_drift": 0}

    for evt in events:
        if evt.severity in severity_counts:
            severity_counts[evt.severity] += 1
        if evt.type in type_counts:
            type_counts[evt.type] += 1

    return {
        "total_events": len(events),
        "severity_breakdown": severity_counts,
        "type_breakdown": type_counts,
        "status": "active",
    }
