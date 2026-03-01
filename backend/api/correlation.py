"""Correlation API — find related signals and build correlation graphs."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_session
from backend.nlp.pipeline import NLPPipeline
from backend.correlation.correlator import SignalCorrelator
from backend.correlation.graph import build_graph
from backend.api.auth import get_required_tenant_id


router = APIRouter(prefix="/api/correlation", tags=["correlation"])

# Shared pipeline + correlator instances
_pipeline = NLPPipeline(use_mock=settings.use_mock_ml)
_correlator = SignalCorrelator(pipeline=_pipeline)


@router.get("/{signal_id}")
async def get_correlations(
    signal_id: int,
    k: int = Query(default=10, ge=1, le=50),
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Find signals correlated to the given signal."""
    correlations = await _correlator.correlate(signal_id, session, tenant_id=tenant_id, k=k)
    return {
        "signal_id": signal_id,
        "correlations": [
            {
                "related_signal_id": c.related_signal_id,
                "score": round(c.score, 4),
                "method": c.method,
                "explanation": c.explanation,
            }
            for c in correlations
        ],
        "total": len(correlations),
    }


@router.get("/graph/{signal_id}")
async def get_correlation_graph(
    signal_id: int,
    depth: int = Query(default=1, ge=1, le=3),
    k: int = Query(default=8, ge=1, le=20),
    tenant_id: str = Depends(get_required_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Build a correlation graph centered on a signal for D3.js visualization."""
    graph = await build_graph(
        center_signal_id=signal_id,
        session=session,
        correlator=_correlator,
        tenant_id=tenant_id,
        depth=depth,
        k_per_node=k,
    )
    return {
        "center_signal_id": signal_id,
        "nodes": [asdict(n) for n in graph.nodes],
        "edges": [asdict(e) for e in graph.edges],
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
    }
