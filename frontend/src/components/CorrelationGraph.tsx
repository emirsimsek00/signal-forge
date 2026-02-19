"use client";

import React, { useEffect, useRef, useCallback, useState } from "react";

interface GraphNode {
    id: number;
    source: string;
    title: string;
    risk_score: number;
    risk_tier: string;
    sentiment_label: string;
    timestamp: string;
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
}

interface GraphEdge {
    source: number;
    target: number;
    weight: number;
    method: string;
    explanation: string;
}

interface CorrelationGraphProps {
    nodes: GraphNode[];
    edges: GraphEdge[];
    centerSignalId: number;
    onNodeClick?: (nodeId: number) => void;
    width?: number;
    height?: number;
}

const SOURCE_COLORS: Record<string, string> = {
    reddit: "#ff4500",
    news: "#1da1f2",
    zendesk: "#03363d",
    stripe: "#635bff",
    pagerduty: "#06ac38",
    system: "#f59e0b",
    financial: "#10b981",
    custom: "#8b5cf6",
};

const TIER_RING_COLORS: Record<string, string> = {
    critical: "#ef4444",
    high: "#f97316",
    moderate: "#eab308",
    low: "#22c55e",
};

export default function CorrelationGraph({
    nodes,
    edges,
    centerSignalId,
    onNodeClick,
    width = 800,
    height = 600,
}: CorrelationGraphProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
    const [tooltip, setTooltip] = useState<{ x: number; y: number } | null>(null);
    const simNodesRef = useRef<GraphNode[]>([]);
    const animRef = useRef<number>(0);
    const dragRef = useRef<{ node: GraphNode | null; offsetX: number; offsetY: number }>({
        node: null,
        offsetX: 0,
        offsetY: 0,
    });

    // Force-directed simulation
    const simulate = useCallback(() => {
        const simNodes = simNodesRef.current;
        if (simNodes.length === 0) return;

        // Apply forces
        for (const edge of edges) {
            const sourceNode = simNodes.find((n) => n.id === edge.source);
            const targetNode = simNodes.find((n) => n.id === edge.target);
            if (!sourceNode || !targetNode) continue;

            const dx = (targetNode.x ?? 0) - (sourceNode.x ?? 0);
            const dy = (targetNode.y ?? 0) - (sourceNode.y ?? 0);
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const idealDist = 120 / (edge.weight + 0.1);
            const force = (dist - idealDist) * 0.005;

            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            sourceNode.vx = (sourceNode.vx ?? 0) + fx;
            sourceNode.vy = (sourceNode.vy ?? 0) + fy;
            targetNode.vx = (targetNode.vx ?? 0) - fx;
            targetNode.vy = (targetNode.vy ?? 0) - fy;
        }

        // Repulsion between all nodes
        for (let i = 0; i < simNodes.length; i++) {
            for (let j = i + 1; j < simNodes.length; j++) {
                const a = simNodes[i];
                const b = simNodes[j];
                const dx = (b.x ?? 0) - (a.x ?? 0);
                const dy = (b.y ?? 0) - (a.y ?? 0);
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const force = 800 / (dist * dist);

                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;

                a.vx = (a.vx ?? 0) - fx;
                a.vy = (a.vy ?? 0) - fy;
                b.vx = (b.vx ?? 0) + fx;
                b.vy = (b.vy ?? 0) + fy;
            }
        }

        // Center gravity
        const cx = width / 2;
        const cy = height / 2;
        for (const node of simNodes) {
            node.vx = (node.vx ?? 0) + ((cx - (node.x ?? 0)) * 0.002);
            node.vy = (node.vy ?? 0) + ((cy - (node.y ?? 0)) * 0.002);

            // Apply velocity with damping
            node.vx! *= 0.9;
            node.vy! *= 0.9;
            node.x = (node.x ?? cx) + (node.vx ?? 0);
            node.y = (node.y ?? cy) + (node.vy ?? 0);

            // Clamp to bounds
            node.x = Math.max(30, Math.min(width - 30, node.x));
            node.y = Math.max(30, Math.min(height - 30, node.y));
        }
    }, [edges, width, height]);

    const draw = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        const simNodes = simNodesRef.current;

        ctx.clearRect(0, 0, width, height);

        // Draw edges
        for (const edge of edges) {
            const sourceNode = simNodes.find((n) => n.id === edge.source);
            const targetNode = simNodes.find((n) => n.id === edge.target);
            if (!sourceNode || !targetNode) continue;

            ctx.beginPath();
            ctx.moveTo(sourceNode.x ?? 0, sourceNode.y ?? 0);
            ctx.lineTo(targetNode.x ?? 0, targetNode.y ?? 0);
            ctx.strokeStyle = `rgba(148, 163, 184, ${0.15 + edge.weight * 0.6})`;
            ctx.lineWidth = 1 + edge.weight * 3;
            ctx.stroke();
        }

        // Draw nodes
        for (const node of simNodes) {
            const x = node.x ?? 0;
            const y = node.y ?? 0;
            const isCenter = node.id === centerSignalId;
            const isHovered = hoveredNode?.id === node.id;
            const radius = isCenter ? 22 : 10 + (node.risk_score ?? 0) * 12;

            // Risk tier ring
            ctx.beginPath();
            ctx.arc(x, y, radius + 3, 0, Math.PI * 2);
            ctx.strokeStyle = TIER_RING_COLORS[node.risk_tier] || "#64748b";
            ctx.lineWidth = isHovered ? 3 : 2;
            ctx.stroke();

            // Node fill
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            const color = SOURCE_COLORS[node.source] || "#8b5cf6";
            ctx.fillStyle = isCenter ? color : `${color}cc`;
            ctx.fill();

            // Center node glow
            if (isCenter) {
                ctx.shadowColor = color;
                ctx.shadowBlur = 15;
                ctx.beginPath();
                ctx.arc(x, y, radius, 0, Math.PI * 2);
                ctx.fill();
                ctx.shadowBlur = 0;
            }

            // Label
            if (isCenter || isHovered || radius > 14) {
                ctx.font = `${isCenter ? "bold " : ""}11px Inter, sans-serif`;
                ctx.fillStyle = "#e2e8f0";
                ctx.textAlign = "center";
                const label = node.title.length > 25 ? node.title.slice(0, 25) + "…" : node.title;
                ctx.fillText(label, x, y + radius + 16);
            }
        }

        simulate();
        animRef.current = requestAnimationFrame(draw);
    }, [edges, centerSignalId, hoveredNode, width, height, simulate]);

    // Initialize simulation nodes
    useEffect(() => {
        const cx = width / 2;
        const cy = height / 2;
        simNodesRef.current = nodes.map((n, i) => ({
            ...n,
            x: n.id === centerSignalId ? cx : cx + Math.cos(i * 0.8) * 150 + Math.random() * 40,
            y: n.id === centerSignalId ? cy : cy + Math.sin(i * 0.8) * 150 + Math.random() * 40,
            vx: 0,
            vy: 0,
        }));

        animRef.current = requestAnimationFrame(draw);
        return () => cancelAnimationFrame(animRef.current);
    }, [nodes, centerSignalId, width, height, draw]);

    // Mouse interactions
    const getNodeAtPosition = useCallback(
        (mx: number, my: number) => {
            for (const node of simNodesRef.current) {
                const dx = (node.x ?? 0) - mx;
                const dy = (node.y ?? 0) - my;
                const radius = node.id === centerSignalId ? 22 : 10 + (node.risk_score ?? 0) * 12;
                if (dx * dx + dy * dy < (radius + 5) * (radius + 5)) return node;
            }
            return null;
        },
        [centerSignalId]
    );

    const handleMouseMove = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            const rect = canvasRef.current?.getBoundingClientRect();
            if (!rect) return;
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            if (dragRef.current.node) {
                dragRef.current.node.x = mx;
                dragRef.current.node.y = my;
                dragRef.current.node.vx = 0;
                dragRef.current.node.vy = 0;
                return;
            }

            const node = getNodeAtPosition(mx, my);
            setHoveredNode(node);
            setTooltip(node ? { x: e.clientX, y: e.clientY } : null);
            if (canvasRef.current) canvasRef.current.style.cursor = node ? "pointer" : "default";
        },
        [getNodeAtPosition]
    );

    const handleMouseDown = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            const rect = canvasRef.current?.getBoundingClientRect();
            if (!rect) return;
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            const node = getNodeAtPosition(mx, my);
            if (node) dragRef.current = { node, offsetX: mx - (node.x ?? 0), offsetY: my - (node.y ?? 0) };
        },
        [getNodeAtPosition]
    );

    const handleMouseUp = useCallback(() => {
        if (dragRef.current.node && onNodeClick) {
            onNodeClick(dragRef.current.node.id);
        }
        dragRef.current = { node: null, offsetX: 0, offsetY: 0 };
    }, [onNodeClick]);

    return (
        <div className="relative">
            <canvas
                ref={canvasRef}
                width={width}
                height={height}
                onMouseMove={handleMouseMove}
                onMouseDown={handleMouseDown}
                onMouseUp={handleMouseUp}
                onMouseLeave={() => {
                    setHoveredNode(null);
                    setTooltip(null);
                    dragRef.current = { node: null, offsetX: 0, offsetY: 0 };
                }}
                style={{ borderRadius: "12px", background: "rgba(15, 23, 42, 0.6)" }}
            />

            {/* Tooltip */}
            {hoveredNode && tooltip && (
                <div
                    className="card-glass"
                    style={{
                        position: "fixed",
                        left: tooltip.x + 12,
                        top: tooltip.y - 60,
                        padding: "10px 14px",
                        zIndex: 100,
                        fontSize: "12px",
                        maxWidth: "280px",
                        pointerEvents: "none",
                    }}
                >
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{hoveredNode.title}</div>
                    <div style={{ color: "var(--text-secondary)", display: "flex", gap: 12 }}>
                        <span className={`badge badge-${hoveredNode.risk_tier}`}>{hoveredNode.risk_tier}</span>
                        <span>{hoveredNode.source}</span>
                        <span>Risk: {((hoveredNode.risk_score ?? 0) * 100).toFixed(0)}%</span>
                    </div>
                </div>
            )}

            {/* Legend */}
            <div
                className="card-glass"
                style={{
                    position: "absolute",
                    bottom: 12,
                    left: 12,
                    padding: "8px 12px",
                    fontSize: "11px",
                    display: "flex",
                    gap: 12,
                    flexWrap: "wrap",
                }}
            >
                {Object.entries(SOURCE_COLORS).map(([source, color]) => (
                    <span key={source} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
                        {source}
                    </span>
                ))}
            </div>
        </div>
    );
}
