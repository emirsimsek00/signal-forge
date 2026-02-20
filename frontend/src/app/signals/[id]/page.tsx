"use client";

import { useEffect, useState, use } from "react";
import { api, SignalExplanation } from "@/lib/api";
import Link from "next/link";
import {
    ArrowLeft, AlertTriangle, TrendingUp, Info, Radio,
    ExternalLink, BarChart3,
} from "lucide-react";

const TIER_COLORS: Record<string, string> = {
    critical: "#f43f5e", high: "#f59e0b", moderate: "#6366f1", low: "#10b981",
};

const COMPONENT_LABELS: Record<string, string> = {
    sentiment: "Sentiment", anomaly: "Anomaly",
    ticket_volume: "Ticket Volume", revenue: "Revenue",
    engagement: "Engagement",
};

export default function SignalDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const [data, setData] = useState<SignalExplanation | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.explainSignal(Number(id)).then(setData).catch(console.error).finally(() => setLoading(false));
    }, [id]);

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                <div className="h-64 skeleton" />
                <div className="h-48 skeleton" />
            </div>
        );
    }
    if (!data) {
        return <div className="glass-card p-12 text-center text-slate-400">Signal not found</div>;
    }

    const { signal, risk_explanation, entities, similar_signals } = data;
    const tierColor = TIER_COLORS[risk_explanation.tier || "low"] || TIER_COLORS.low;

    // Sort components by weighted contribution
    const sortedComponents = Object.entries(risk_explanation.components)
        .sort(([, a], [, b]) => b.weighted - a.weighted);

    const maxWeighted = sortedComponents.length > 0 ? sortedComponents[0][1].weighted : 1;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Link href="/signals" className="p-2 rounded-lg hover:bg-white/5 transition">
                    <ArrowLeft className="w-5 h-5 text-slate-400" />
                </Link>
                <div className="flex-1">
                    <h1 className="text-xl font-bold text-white tracking-tight">
                        {signal.title || `Signal #${signal.id}`}
                    </h1>
                    <div className="flex items-center gap-3 mt-1">
                        <span className={`source-badge source-${signal.source}`}>{signal.source}</span>
                        <span className="text-xs text-slate-500">
                            {new Date(signal.timestamp).toLocaleString()}
                        </span>
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-2xl font-bold" style={{ color: tierColor }}>
                        {((risk_explanation.composite_score || 0) * 100).toFixed(0)}
                    </div>
                    <span className={`badge badge-${risk_explanation.tier}`}>
                        {risk_explanation.tier}
                    </span>
                </div>
            </div>

            {/* Signal content */}
            <div className="glass-card p-5">
                <p className="text-sm text-slate-300 leading-relaxed">{signal.content}</p>
                {signal.summary && signal.summary !== signal.content && (
                    <div className="mt-3 pt-3" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                        <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">AI Summary</p>
                        <p className="text-sm text-slate-400">{signal.summary}</p>
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Risk breakdown */}
                <div className="glass-card p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
                            Why This Risk Score?
                        </h3>
                    </div>

                    <p className="text-sm text-slate-400 mb-4">{risk_explanation.explanation}</p>

                    <div className="space-y-3">
                        {sortedComponents.map(([key, comp]) => (
                            <div key={key}>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-slate-400">{COMPONENT_LABELS[key] || key}</span>
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-slate-500">
                                            {(comp.score * 100).toFixed(0)} × {(comp.weight * 100).toFixed(0)}%
                                        </span>
                                        <span className="text-xs font-semibold text-white">
                                            {(comp.weighted * 100).toFixed(1)}
                                        </span>
                                    </div>
                                </div>
                                <div className="h-2 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
                                    <div className="h-2 rounded-full transition-all duration-500"
                                        style={{
                                            width: `${maxWeighted > 0 ? (comp.weighted / maxWeighted) * 100 : 0}%`,
                                            background: `linear-gradient(90deg, ${tierColor}88, ${tierColor})`,
                                        }} />
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="mt-4 pt-3 flex items-center gap-2" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                        <Info className="w-3.5 h-3.5 text-indigo-400" />
                        <span className="text-xs text-slate-500">
                            Confidence: {((risk_explanation.composite_score || 0) * 100).toFixed(0)}% · Weights sum to{" "}
                            {(Object.values(risk_explanation.weights).reduce((a, b) => a + b, 0) * 100).toFixed(0)}%
                        </span>
                    </div>
                </div>

                {/* Entities */}
                <div className="space-y-6">
                    {entities.length > 0 && (
                        <div className="glass-card p-5">
                            <div className="flex items-center gap-2 mb-3">
                                <Radio className="w-4 h-4 text-cyan-400" />
                                <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Entities</h3>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {entities.map((e, i) => (
                                    <span key={i} className="px-2.5 py-1 rounded-lg text-xs font-medium"
                                        style={{ background: "rgba(6,182,212,0.12)", color: "#22d3ee", border: "1px solid rgba(6,182,212,0.2)" }}>
                                        {e.text} <span className="text-cyan-600 ml-1">{e.label}</span>
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Sentiment */}
                    <div className="glass-card p-5">
                        <div className="flex items-center gap-2 mb-3">
                            <TrendingUp className="w-4 h-4 text-indigo-400" />
                            <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Sentiment</h3>
                        </div>
                        <div className="flex items-center gap-4">
                            <div className="text-3xl font-bold" style={{ color: (signal.sentiment_score || 0) < -0.2 ? "#f43f5e" : (signal.sentiment_score || 0) > 0.2 ? "#10b981" : "#6366f1" }}>
                                {((signal.sentiment_score || 0) * 100).toFixed(0)}%
                            </div>
                            <div>
                                <span className={`badge ${(signal.sentiment_label === "negative") ? "badge-critical" : (signal.sentiment_label === "positive") ? "badge-low" : "badge-moderate"}`}>
                                    {signal.sentiment_label || "neutral"}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Similar signals */}
            {similar_signals.length > 0 && (
                <div className="glass-card p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <BarChart3 className="w-4 h-4 text-violet-400" />
                        <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
                            Related Signals
                        </h3>
                    </div>
                    <div className="space-y-2">
                        {similar_signals.map((sim) => (
                            <Link key={sim.id} href={`/signals/${sim.id}`}
                                className="flex items-center justify-between px-4 py-3 rounded-xl transition-all hover:bg-white/5"
                                style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}>
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                    <span className={`source-badge source-${sim.source}`}>{sim.source}</span>
                                    <span className="text-sm text-slate-300 truncate">{sim.title || `Signal #${sim.id}`}</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <span className={`badge badge-${sim.risk_tier || "low"}`}>{sim.risk_tier}</span>
                                    <span className="text-xs text-slate-500 font-mono">{(sim.similarity * 100).toFixed(0)}% match</span>
                                    <ExternalLink className="w-3.5 h-3.5 text-slate-600" />
                                </div>
                            </Link>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
