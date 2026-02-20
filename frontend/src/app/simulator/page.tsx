"use client";

import { useState } from "react";
import { api, ScenarioResult } from "@/lib/api";
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { FlaskConical, TrendingUp, TrendingDown, Minus, Loader2, Zap } from "lucide-react";

const TIER_COLORS: Record<string, string> = {
    critical: "#f43f5e", high: "#f59e0b", moderate: "#6366f1", low: "#10b981",
};

export default function SimulatorPage() {
    const [sentimentShift, setSentimentShift] = useState(0);
    const [result, setResult] = useState<ScenarioResult | null>(null);
    const [loading, setLoading] = useState(false);

    const runScenario = async () => {
        setLoading(true);
        try {
            const res = await api.runScenario({ sentiment_shift: sentimentShift / 100 });
            setResult(res);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    };

    const baselineChart = result
        ? Object.entries(result.baseline_tier_distribution).map(([tier, count]) => ({ tier, count, fill: TIER_COLORS[tier] || "#6366f1" }))
        : [];
    const projectedChart = result
        ? Object.entries(result.projected_tier_distribution).map(([tier, count]) => ({ tier, count, fill: TIER_COLORS[tier] || "#6366f1" }))
        : [];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">Scenario Simulator</h1>
                <p className="text-sm text-slate-500 mt-1">Forecast risk impact of hypothetical changes</p>
            </div>

            <div className="glass-card p-6">
                <div className="flex items-center gap-2 mb-6">
                    <FlaskConical className="w-4 h-4 text-violet-400" />
                    <h3 className="text-sm font-semibold text-white uppercase tracking-wider">What If...</h3>
                </div>

                <div className="space-y-6">
                    <div>
                        <label className="text-sm text-slate-300 block mb-2">
                            Sentiment shifts by <span className="font-semibold text-white">{sentimentShift > 0 ? "+" : ""}{sentimentShift}%</span>
                        </label>
                        <input type="range" min="-50" max="50" step="5" value={sentimentShift}
                            onChange={(e) => setSentimentShift(Number(e.target.value))}
                            className="w-full accent-indigo-500" />
                        <div className="flex justify-between text-xs text-slate-600 mt-1">
                            <span>−50% (very negative)</span>
                            <span>0 (no change)</span>
                            <span>+50% (very positive)</span>
                        </div>
                    </div>

                    <button onClick={runScenario} disabled={loading}
                        className="btn-primary inline-flex items-center gap-2">
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                        Run Simulation
                    </button>
                </div>
            </div>

            {result && (
                <div className="space-y-6">
                    {/* Impact summary */}
                    <div className="grid grid-cols-3 gap-4">
                        <div className="kpi-card">
                            <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Baseline Risk</p>
                            <p className="text-2xl font-bold text-white">{(result.baseline_avg_risk * 100).toFixed(1)}%</p>
                        </div>
                        <div className="kpi-card">
                            <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Projected Risk</p>
                            <p className="text-2xl font-bold" style={{ color: result.delta > 0 ? "#f43f5e" : result.delta < 0 ? "#10b981" : "#6366f1" }}>
                                {(result.projected_avg_risk * 100).toFixed(1)}%
                            </p>
                        </div>
                        <div className="kpi-card">
                            <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Delta</p>
                            <div className="flex items-center gap-2">
                                {result.delta > 0.001 ? <TrendingUp className="w-5 h-5 text-rose-400" /> :
                                    result.delta < -0.001 ? <TrendingDown className="w-5 h-5 text-emerald-400" /> :
                                        <Minus className="w-5 h-5 text-indigo-400" />}
                                <p className="text-2xl font-bold" style={{ color: result.delta > 0 ? "#f43f5e" : result.delta < 0 ? "#10b981" : "#6366f1" }}>
                                    {result.delta > 0 ? "+" : ""}{(result.delta * 100).toFixed(2)}%
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Distribution comparison */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="glass-card p-5">
                            <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Baseline Distribution</h3>
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={baselineChart}>
                                    <XAxis dataKey="tier" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                                    <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "#f1f5f9" }} />
                                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                                        {baselineChart.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="glass-card p-5">
                            <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Projected Distribution</h3>
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={projectedChart}>
                                    <XAxis dataKey="tier" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                                    <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "#f1f5f9" }} />
                                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                                        {projectedChart.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="glass-card p-4 text-center text-sm text-slate-400">
                        Analyzed {result.signals_analyzed} signals · High/critical change: <span className={`font-semibold ${result.high_risk_change > 0 ? "text-rose-400" : result.high_risk_change < 0 ? "text-emerald-400" : "text-slate-400"}`}>
                            {result.high_risk_change > 0 ? "+" : ""}{result.high_risk_change}
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}
