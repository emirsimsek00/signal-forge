"use client";

import { useState, useCallback } from "react";
import { api, type CorrelationGraphData, type Signal } from "@/lib/api";
import CorrelationGraph from "@/components/CorrelationGraph";
import { Search, GitBranch, Loader, Info } from "lucide-react";

export default function CorrelationPage() {
    const [signalId, setSignalId] = useState("");
    const [graphData, setGraphData] = useState<CorrelationGraphData | null>(null);
    const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [depth, setDepth] = useState(1);

    const loadGraph = useCallback(async (id: number) => {
        setLoading(true);
        setError("");
        try {
            const data = await api.getCorrelationGraph(id, depth);
            setGraphData(data);
            const signal = await api.getSignal(id);
            setSelectedSignal(signal);
        } catch {
            setError("Could not load correlation graph. Make sure the signal ID exists.");
            setGraphData(null);
        } finally {
            setLoading(false);
        }
    }, [depth]);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        const id = parseInt(signalId);
        if (!isNaN(id) && id > 0) loadGraph(id);
    };

    const handleNodeClick = useCallback(
        async (nodeId: number) => {
            try {
                const signal = await api.getSignal(nodeId);
                setSelectedSignal(signal);
            } catch {
                // ignore
            }
        },
        []
    );

    return (
        <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
                <GitBranch size={28} style={{ color: "var(--accent-primary)" }} />
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700 }}>Signal Correlations</h1>
                    <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>
                        Discover relationships between signals using semantic similarity, temporal proximity, and entity co-occurrence
                    </p>
                </div>
            </div>

            {/* Search bar */}
            <form onSubmit={handleSearch} className="card-glass" style={{ padding: 16, marginBottom: 24, display: "flex", gap: 12, alignItems: "center" }}>
                <Search size={18} style={{ color: "var(--text-secondary)" }} />
                <input
                    type="number"
                    placeholder="Enter Signal ID..."
                    value={signalId}
                    onChange={(e) => setSignalId(e.target.value)}
                    style={{
                        flex: 1,
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 8,
                        padding: "8px 12px",
                        color: "var(--text-primary)",
                        fontSize: 14,
                    }}
                />
                <select
                    value={depth}
                    onChange={(e) => setDepth(Number(e.target.value))}
                    style={{
                        background: "rgba(255,255,255,0.05)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 8,
                        padding: "8px 12px",
                        color: "var(--text-primary)",
                        fontSize: 14,
                    }}
                >
                    <option value={1}>Depth: 1</option>
                    <option value={2}>Depth: 2</option>
                    <option value={3}>Depth: 3</option>
                </select>
                <button type="submit" className="btn-primary" disabled={loading}>
                    {loading ? <Loader className="animate-spin" size={16} /> : "Search"}
                </button>
            </form>

            {error && (
                <div className="card-glass" style={{ padding: 16, marginBottom: 24, color: "#f87171", display: "flex", gap: 8, alignItems: "center" }}>
                    <Info size={16} /> {error}
                </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 24 }}>
                {/* Graph */}
                <div className="card-glass" style={{ padding: 16, minHeight: 500 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "var(--text-secondary)" }}>
                        Correlation Graph
                        {graphData && (
                            <span style={{ fontWeight: 400, marginLeft: 8 }}>
                                ({graphData.node_count} nodes, {graphData.edge_count} edges)
                            </span>
                        )}
                    </h3>
                    {graphData && graphData.nodes.length > 0 ? (
                        <CorrelationGraph
                            nodes={graphData.nodes}
                            edges={graphData.edges}
                            centerSignalId={graphData.center_signal_id}
                            onNodeClick={handleNodeClick}
                            width={700}
                            height={500}
                        />
                    ) : !loading ? (
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 400, color: "var(--text-secondary)" }}>
                            <GitBranch size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
                            <p>Enter a Signal ID to visualize its correlations</p>
                        </div>
                    ) : (
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 400 }}>
                            <Loader className="animate-spin" size={32} style={{ color: "var(--accent-primary)" }} />
                        </div>
                    )}
                </div>

                {/* Detail panel */}
                <div className="card-glass" style={{ padding: 16 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "var(--text-secondary)" }}>
                        Signal Detail
                    </h3>
                    {selectedSignal ? (
                        <div style={{ fontSize: 13 }}>
                            <div style={{ marginBottom: 12 }}>
                                <span style={{ color: "var(--text-secondary)" }}>ID:</span>{" "}
                                <span style={{ fontWeight: 600 }}>#{selectedSignal.id}</span>
                            </div>
                            <div style={{ marginBottom: 12 }}>
                                <span style={{ color: "var(--text-secondary)" }}>Source:</span>{" "}
                                <span className={`badge badge-${selectedSignal.source}`}>{selectedSignal.source}</span>
                            </div>
                            <div style={{ marginBottom: 12 }}>
                                <span style={{ color: "var(--text-secondary)" }}>Risk:</span>{" "}
                                <span className={`badge badge-${selectedSignal.risk_tier}`}>
                                    {selectedSignal.risk_tier} ({((selectedSignal.risk_score ?? 0) * 100).toFixed(0)}%)
                                </span>
                            </div>
                            <div style={{ marginBottom: 12 }}>
                                <span style={{ color: "var(--text-secondary)" }}>Sentiment:</span>{" "}
                                <span>{selectedSignal.sentiment_label}</span>
                            </div>
                            <div style={{ marginBottom: 16 }}>
                                <span style={{ color: "var(--text-secondary)" }}>Title:</span>
                                <div style={{ marginTop: 4, fontWeight: 500 }}>{selectedSignal.title || "—"}</div>
                            </div>
                            <div>
                                <span style={{ color: "var(--text-secondary)" }}>Content:</span>
                                <div style={{
                                    marginTop: 4,
                                    background: "rgba(255,255,255,0.03)",
                                    borderRadius: 8,
                                    padding: 10,
                                    lineHeight: 1.5,
                                    maxHeight: 200,
                                    overflow: "auto",
                                }}>
                                    {selectedSignal.content}
                                </div>
                            </div>

                            {/* Correlation list */}
                            {graphData && (
                                <div style={{ marginTop: 16, borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 12 }}>
                                    <h4 style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: "var(--text-secondary)" }}>
                                        Connected Signals
                                    </h4>
                                    {graphData.edges
                                        .filter((e) => e.source === selectedSignal.id || e.target === selectedSignal.id)
                                        .sort((a, b) => b.weight - a.weight)
                                        .slice(0, 8)
                                        .map((edge, i) => {
                                            const otherId = edge.source === selectedSignal.id ? edge.target : edge.source;
                                            const otherNode = graphData.nodes.find((n) => n.id === otherId);
                                            return (
                                                <div
                                                    key={i}
                                                    onClick={() => handleNodeClick(otherId)}
                                                    style={{
                                                        padding: "6px 0",
                                                        fontSize: 12,
                                                        cursor: "pointer",
                                                        borderBottom: "1px solid rgba(255,255,255,0.05)",
                                                    }}
                                                >
                                                    <div style={{ fontWeight: 500 }}>#{otherId}: {otherNode?.title?.slice(0, 40) || "—"}</div>
                                                    <div style={{ color: "var(--text-secondary)", fontSize: 11, marginTop: 2 }}>
                                                        {edge.method} — {(edge.weight * 100).toFixed(0)}% match
                                                    </div>
                                                </div>
                                            );
                                        })}
                                </div>
                            )}
                        </div>
                    ) : (
                        <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>Click a node to view details</p>
                    )}
                </div>
            </div>
        </div>
    );
}
