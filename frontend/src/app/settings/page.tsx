"use client";

import { useEffect, useState } from "react";
import { api, RiskWeights, AppSettings } from "@/lib/api";
import { Settings2, Save, RotateCcw, Loader2, CheckCircle2, Sliders } from "lucide-react";

const WEIGHT_LABELS: Record<string, { label: string; desc: string; color: string }> = {
    sentiment: { label: "Sentiment", desc: "Community & customer mood analysis", color: "#f43f5e" },
    anomaly: { label: "Anomaly", desc: "Statistical deviation from baseline", color: "#f59e0b" },
    ticket_volume: { label: "Ticket Volume", desc: "Support ticket frequency & urgency", color: "#6366f1" },
    revenue: { label: "Revenue", desc: "Payment failures, churn indicators", color: "#10b981" },
    engagement: { label: "Engagement", desc: "Discussion volume & virality", color: "#06b6d4" },
};

export default function SettingsPage() {
    const [weights, setWeights] = useState<RiskWeights | null>(null);
    const [settings, setSettings] = useState<AppSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([api.getRiskWeights(), api.getSettings()])
            .then(([w, s]) => { setWeights(w); setSettings(s); })
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const total = weights ? Object.values(weights).reduce((a, b) => a + b, 0) : 0;
    const validTotal = Math.abs(total - 1.0) <= 0.02;

    const updateWeight = (key: keyof RiskWeights, value: number) => {
        if (!weights) return;
        setWeights({ ...weights, [key]: value });
        setSaved(false);
        setError(null);
    };

    const saveWeights = async () => {
        if (!weights) return;
        setSaving(true);
        setError(null);
        try {
            const updated = await api.updateRiskWeights(weights);
            setWeights(updated);
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to save");
        }
        finally { setSaving(false); }
    };

    const resetWeights = async () => {
        setSaving(true);
        try {
            const defaults = await api.resetRiskWeights();
            setWeights(defaults);
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } catch (e) { console.error(e); }
        finally { setSaving(false); }
    };

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                {[...Array(5)].map((_, i) => <div key={i} className="h-24 skeleton" />)}
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">Settings</h1>
                <p className="text-sm text-slate-500 mt-1">Configure risk weights and system preferences</p>
            </div>

            {/* Risk Weights */}
            <div className="glass-card p-6">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-2">
                        <Sliders className="w-4 h-4 text-indigo-400" />
                        <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Risk Weights</h3>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className={`text-xs font-mono ${validTotal ? "text-emerald-400" : "text-rose-400"}`}>
                            Total: {(total * 100).toFixed(0)}%
                        </span>
                    </div>
                </div>

                <div className="space-y-5">
                    {weights && Object.entries(WEIGHT_LABELS).map(([key, meta]) => {
                        const value = weights[key as keyof RiskWeights];
                        return (
                            <div key={key}>
                                <div className="flex items-center justify-between mb-2">
                                    <div>
                                        <span className="text-sm font-medium text-white">{meta.label}</span>
                                        <span className="text-xs text-slate-500 ml-2">{meta.desc}</span>
                                    </div>
                                    <span className="text-sm font-mono font-semibold text-white">{(value * 100).toFixed(0)}%</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <input type="range" min="0" max="60" step="1"
                                        value={value * 100}
                                        onChange={(e) => updateWeight(key as keyof RiskWeights, Number(e.target.value) / 100)}
                                        className="flex-1 accent-indigo-500" />
                                    <div className="w-16 h-2 rounded-full" style={{ background: "rgba(255,255,255,0.06)" }}>
                                        <div className="h-2 rounded-full transition-all" style={{ width: `${(value / 0.6) * 100}%`, background: meta.color }} />
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {error && <div className="mt-4 px-4 py-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-sm text-rose-300">{error}</div>}

                <div className="flex items-center gap-3 mt-6 pt-4" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                    <button onClick={saveWeights} disabled={saving || !validTotal}
                        className="btn-primary inline-flex items-center gap-2 disabled:opacity-50">
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                        {saved ? "Saved!" : "Save Weights"}
                    </button>
                    <button onClick={resetWeights} disabled={saving}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm text-slate-300 hover:border-indigo-400/50 transition disabled:opacity-50">
                        <RotateCcw className="w-3.5 h-3.5" /> Reset
                    </button>
                </div>
            </div>

            {/* System Info */}
            {settings && (
                <div className="glass-card p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Settings2 className="w-4 h-4 text-cyan-400" />
                        <h3 className="text-sm font-semibold text-white uppercase tracking-wider">System</h3>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        {[
                            { label: "ML Mode", value: settings.use_mock_ml ? "Mock" : "Live", color: settings.use_mock_ml ? "#f59e0b" : "#10b981" },
                            { label: "LLM Chat", value: settings.llm_enabled ? "Enabled" : "Disabled", color: settings.llm_enabled ? "#10b981" : "#64748b" },
                            { label: "Data Retention", value: `${settings.retention_days} days`, color: "#6366f1" },
                        ].map((item) => (
                            <div key={item.label} className="flex items-center justify-between px-4 py-3 rounded-xl"
                                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                                <span className="text-sm text-slate-400">{item.label}</span>
                                <span className="text-sm font-medium" style={{ color: item.color }}>{item.value}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
