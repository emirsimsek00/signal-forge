"""Correlation graph builder for force-directed visualization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.signal import Signal
from backend.correlation.correlator import SignalCorrelator, CorrelationResult


@dataclass
class GraphNode:
    id: int
    source: str
    title: str
    risk_score: float
    risk_tier: str
    sentiment_label: str
    timestamp: str


@dataclass
class GraphEdge:
    source: int  # node id
    target: int  # node id
    weight: float
    method: str
    explanation: str


@dataclass
class CorrelationGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


async def build_graph(
    center_signal_id: int,
    session: AsyncSession,
    correlator: SignalCorrelator,
    depth: int = 1,
    k_per_node: int = 8,
) -> CorrelationGraph:
    """Build a correlation graph centered on a signal.

    Args:
        center_signal_id: The signal to center the graph on.
        depth: How many hops out to expand (1 = direct neighbors only).
        k_per_node: Max correlations per node.
    """
    visited: set[int] = set()
    nodes_map: dict[int, GraphNode] = {}
    edges: list[GraphEdge] = []

    # BFS expansion
    queue = [center_signal_id]
    for current_depth in range(depth):
        next_queue: list[int] = []
        for sig_id in queue:
            if sig_id in visited:
                continue
            visited.add(sig_id)

            # Add node
            if sig_id not in nodes_map:
                node = await _make_node(sig_id, session)
                if node:
                    nodes_map[sig_id] = node

            # Find correlations
            correlations = await correlator.correlate(sig_id, session, k=k_per_node)

            for corr in correlations:
                # Add edge
                edges.append(GraphEdge(
                    source=corr.signal_id,
                    target=corr.related_signal_id,
                    weight=corr.score,
                    method=corr.method,
                    explanation=corr.explanation,
                ))

                # Add related node
                if corr.related_signal_id not in nodes_map:
                    node = await _make_node(corr.related_signal_id, session)
                    if node:
                        nodes_map[corr.related_signal_id] = node

                # Queue for next depth
                if corr.related_signal_id not in visited:
                    next_queue.append(corr.related_signal_id)

        queue = next_queue

    # Deduplicate edges (keep highest weight for each pair)
    edge_map: dict[tuple[int, int], GraphEdge] = {}
    for edge in edges:
        key = (min(edge.source, edge.target), max(edge.source, edge.target))
        if key not in edge_map or edge.weight > edge_map[key].weight:
            edge_map[key] = edge

    return CorrelationGraph(
        nodes=list(nodes_map.values()),
        edges=list(edge_map.values()),
    )


async def _make_node(signal_id: int, session: AsyncSession) -> Optional[GraphNode]:
    stmt = select(Signal).where(Signal.id == signal_id)
    result = await session.execute(stmt)
    sig = result.scalar_one_or_none()
    if not sig:
        return None

    return GraphNode(
        id=sig.id,
        source=sig.source,
        title=sig.title or sig.content[:60],
        risk_score=sig.risk_score or 0.0,
        risk_tier=sig.risk_tier or "low",
        sentiment_label=sig.sentiment_label or "neutral",
        timestamp=sig.timestamp.isoformat() if sig.timestamp else "",
    )
