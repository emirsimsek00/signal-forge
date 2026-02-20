"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ExecutiveBrief } from "@/lib/api";
import { FileText, Shield, AlertTriangle, Lightbulb, ArrowRight, RefreshCw } from "lucide-react";

type ToneMode = "executive_concise" | "technical_detailed" | "customer_facing";

const TONE_LABELS: Record<ToneMode, string> = {
    executive_concise: "Executive Concise",
    technical_detailed: "Technical Detailed",
    customer_facing: "Customer Facing",
};

export default function BriefPage() {
    const [brief, setBrief] = useState<ExecutiveBrief | null>(null);
    const [tone, setTone] = useState<ToneMode>("executive_concise");
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchBrief = useCallback(async (toneMode: ToneMode) => {
        try {
            const data = await api.generateBrief(toneMode, 24);
            setBrief(data);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        setLoading(true);
        fetchBrief(tone);
    }, [tone, fetchBrief]);

    const refresh = async () => {
        setRefreshing(true);
        await fetchBrief(tone);
    };

    if (loading || !brief) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                <div className="h-40 skeleton" />
                <div className="h-60 skeleton" />
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-4xl">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">Executive Brief</h1>
                    <p className="text-sm text-slate-500 mt-1">AI-generated intelligence summary</p>
                </div>
                <div className="flex items-center gap-3">
                    <select
                        value={tone}
                        onChange={(e) => setTone(e.target.value as ToneMode)}
                        className="text-xs rounded-lg px-3 py-2 border border-white/10 bg-white/5 text-slate-300"
                    >
                        {Object.entries(TONE_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>
                                {label}
                            </option>
                        ))}
                    </select>
                    <button onClick={refresh} className="btn-primary flex items-center gap-2" disabled={refreshing}>
                        <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
                        Refresh
                    </button>
                </div>
            </div>

            <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">Confidence:</span>
                <div className="w-32 h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                        className="h-full rounded-full"
                        style={{
                            width: `${brief.confidence_score * 100}%`,
                            background:
                                brief.confidence_score > 0.8
                                    ? "var(--accent-emerald)"
                                    : brief.confidence_score > 0.6
                                        ? "var(--accent-amber)"
                                        : "var(--accent-rose)",
                        }}
                    />
                </div>
                <span className="text-xs font-mono text-slate-400">{(brief.confidence_score * 100).toFixed(0)}%</span>
                <span className="text-xs text-slate-600 ml-2">
                    Generated {new Date(brief.generated_at).toLocaleString()}
                </span>
            </div>

            {/* Situation Overview */}
            <div className="glass-card p-6 relative overflow-hidden" style={{ borderLeft: "3px solid var(--accent-indigo)" }}>
                <div className="absolute top-0 right-0 w-32 h-32 opacity-5" style={{ background: "var(--gradient-primary)", borderRadius: "0 0 0 100%" }} />
                <div className="flex items-center gap-2 mb-3">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Situation Overview</h2>
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">{brief.situation_overview}</p>
            </div>

            {/* Key Risk Indicators */}
            <div className="glass-card p-6" style={{ borderLeft: "3px solid var(--accent-amber)" }}>
                <div className="flex items-center gap-2 mb-4">
                    <Shield className="w-4 h-4 text-amber-400" />
                    <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Key Risk Indicators</h2>
                </div>
                <div className="space-y-3">
                    {brief.key_risk_indicators.map((indicator, i) => (
                        <div key={i} className="flex items-start gap-3">
                            <div className="w-6 h-6 rounded-md flex items-center justify-center shrink-0 mt-0.5" style={{ background: "rgba(245, 158, 11, 0.1)" }}>
                                <span className="text-[0.65rem] font-bold text-amber-400">{i + 1}</span>
                            </div>
                            <p className="text-sm text-slate-300">{indicator}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Root Cause Hypotheses */}
            <div className="glass-card p-6" style={{ borderLeft: "3px solid var(--accent-violet)" }}>
                <div className="flex items-center gap-2 mb-4">
                    <Lightbulb className="w-4 h-4 text-violet-400" />
                    <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Root-Cause Hypotheses</h2>
                </div>
                <div className="space-y-3">
                    {brief.root_cause_hypotheses.map((h, i) => (
                        <div key={i} className="flex items-start gap-3">
                            <ArrowRight className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
                            <p className="text-sm text-slate-300">{h}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Recommended Actions */}
            <div className="glass-card p-6" style={{ borderLeft: "3px solid var(--accent-emerald)" }}>
                <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Recommended Actions</h2>
                </div>
                <div className="space-y-3">
                    {brief.recommended_actions.map((r, i) => (
                        <div key={i} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: "rgba(16, 185, 129, 0.05)" }}>
                            <div className="w-6 h-6 rounded-md flex items-center justify-center shrink-0" style={{ background: "rgba(16, 185, 129, 0.15)" }}>
                                <span className="text-[0.65rem] font-bold text-emerald-400">{i + 1}</span>
                            </div>
                            <p className="text-sm text-slate-300">{r}</p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="glass-card p-6">
                <h2 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Top Risk Signals</h2>
                <div className="space-y-2">
                    {brief.top_risk_signals.map((signal) => (
                        <div key={signal.id} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: "rgba(255, 255, 255, 0.02)" }}>
                            <span className={`source-badge source-${signal.source}`}>{signal.source}</span>
                            <span className="flex-1 text-sm text-slate-300 truncate">{signal.title}</span>
                            <span className={`badge badge-${signal.risk_tier}`}>{signal.risk_score.toFixed(3)}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
