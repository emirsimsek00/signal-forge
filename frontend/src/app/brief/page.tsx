"use client";

import { useEffect, useState } from "react";
import { api, DashboardOverview, RiskOverview } from "@/lib/api";
import { FileText, Shield, AlertTriangle, Lightbulb, ArrowRight } from "lucide-react";

export default function BriefPage() {
    const [dashboard, setDashboard] = useState<DashboardOverview | null>(null);
    const [risk, setRisk] = useState<RiskOverview | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([api.dashboardOverview(), api.riskOverview()])
            .then(([d, r]) => {
                setDashboard(d);
                setRisk(r);
            })
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                <div className="h-40 skeleton" />
                <div className="h-60 skeleton" />
            </div>
        );
    }

    const topSource = dashboard?.source_distribution[0];
    const criticalSignals = risk?.top_risks.filter((r) => r.risk_tier === "critical") || [];
    const highSignals = risk?.top_risks.filter((r) => r.risk_tier === "high") || [];

    // Generate dynamic brief sections
    const situationOverview = `
    SignalForge has analyzed ${dashboard?.total_signals.toLocaleString()} signals across ${dashboard?.source_distribution.length} active sources.
    The current average risk score is ${risk?.average_score.toFixed(3)} (${risk?.trend} trend).
    ${risk?.critical_count || 0} critical and ${risk?.high_count || 0} high-severity signals have been detected.
    ${dashboard?.active_incidents || 0} incidents are currently active.
  `.trim().replace(/\s+/g, ' ');

    const riskIndicators = [
        risk?.critical_count ? `${risk.critical_count} critical-tier signal(s) detected requiring immediate review` : null,
        risk?.high_count ? `${risk.high_count} high-tier signal(s) with elevated risk scores` : null,
        topSource ? `Highest signal volume from ${topSource.source} (${topSource.count} signals)` : null,
        dashboard?.avg_risk_score && dashboard.avg_risk_score > 0.5 ? "Average risk score exceeds 0.50 — elevated operational risk" : null,
        dashboard?.avg_risk_score && dashboard.avg_risk_score <= 0.25 ? "Overall risk profile is within acceptable range" : null,
    ].filter(Boolean);

    const hypotheses = [
        criticalSignals.length > 0 ? `Critical signals from ${[...new Set(criticalSignals.map(s => s.source))].join(", ")} sources may indicate a systemic issue` : null,
        "Negative sentiment spikes in social channels may precede support ticket volume increases",
        "System metric anomalies should be cross-referenced with recent deployments",
        highSignals.length > 2 ? "Multiple high-severity signals suggest correlated upstream event" : "Signal patterns are within expected variance",
    ].filter(Boolean);

    const recommendations = [
        risk?.critical_count ? "Prioritize investigation of critical-tier signals immediately" : null,
        "Run correlation analysis across sources to identify linked events",
        "Schedule executive review if risk trend continues upward",
        "Consider adjusting alert thresholds based on current baseline",
        dashboard?.active_incidents ? "Triage active incidents and assign investigation owners" : null,
    ].filter(Boolean);

    const confidenceScore = Math.max(0.6, Math.min(0.95, 1 - (risk?.average_score || 0)));

    return (
        <div className="space-y-6 max-w-4xl">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">Executive Brief</h1>
                    <p className="text-sm text-slate-500 mt-1">AI-generated intelligence summary</p>
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500">Confidence:</span>
                    <div className="w-24 h-2 rounded-full bg-white/5 overflow-hidden">
                        <div
                            className="h-full rounded-full"
                            style={{
                                width: `${confidenceScore * 100}%`,
                                background: confidenceScore > 0.8 ? "var(--accent-emerald)" : confidenceScore > 0.6 ? "var(--accent-amber)" : "var(--accent-rose)",
                            }}
                        />
                    </div>
                    <span className="text-xs font-mono text-slate-400">{(confidenceScore * 100).toFixed(0)}%</span>
                </div>
            </div>

            {/* Situation Overview */}
            <div className="glass-card p-6 relative overflow-hidden" style={{ borderLeft: "3px solid var(--accent-indigo)" }}>
                <div className="absolute top-0 right-0 w-32 h-32 opacity-5" style={{ background: "var(--gradient-primary)", borderRadius: "0 0 0 100%" }} />
                <div className="flex items-center gap-2 mb-3">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Situation Overview</h2>
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">{situationOverview}</p>
            </div>

            {/* Key Risk Indicators */}
            <div className="glass-card p-6" style={{ borderLeft: "3px solid var(--accent-amber)" }}>
                <div className="flex items-center gap-2 mb-4">
                    <Shield className="w-4 h-4 text-amber-400" />
                    <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Key Risk Indicators</h2>
                </div>
                <div className="space-y-3">
                    {riskIndicators.map((indicator, i) => (
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
                    {hypotheses.map((h, i) => (
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
                    {recommendations.map((r, i) => (
                        <div key={i} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: "rgba(16, 185, 129, 0.05)" }}>
                            <div className="w-6 h-6 rounded-md flex items-center justify-center shrink-0" style={{ background: "rgba(16, 185, 129, 0.15)" }}>
                                <span className="text-[0.65rem] font-bold text-emerald-400">{i + 1}</span>
                            </div>
                            <p className="text-sm text-slate-300">{r}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Footer */}
            <div className="text-center py-4">
                <p className="text-xs text-slate-600">
                    Generated by SignalForge AI · Executive Concise Mode · {new Date().toLocaleString()}
                </p>
            </div>
        </div>
    );
}
