"use client";

import { useEffect, useState } from "react";
import { api, RiskOverview, HeatmapData } from "@/lib/api";
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { Shield, TrendingUp, AlertTriangle } from "lucide-react";

const TIER_COLORS: Record<string, string> = {
    critical: "#f43f5e",
    high: "#f59e0b",
    moderate: "#6366f1",
    low: "#10b981",
};

const SOURCES = ["reddit", "news", "zendesk", "system", "financial"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function getHeatColor(score: number): string {
    if (score >= 0.75) return "rgba(244, 63, 94, 0.7)";
    if (score >= 0.5) return "rgba(245, 158, 11, 0.6)";
    if (score >= 0.25) return "rgba(99, 102, 241, 0.4)";
    if (score > 0) return "rgba(16, 185, 129, 0.25)";
    return "rgba(255, 255, 255, 0.03)";
}

export default function RiskPage() {
    const [overview, setOverview] = useState<RiskOverview | null>(null);
    const [heatmap, setHeatmap] = useState<HeatmapData | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([api.riskOverview(), api.riskHeatmap()])
            .then(([o, h]) => {
                setOverview(o);
                setHeatmap(h);
            })
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-48 skeleton" />
                <div className="grid grid-cols-4 gap-4">
                    {[...Array(4)].map((_, i) => <div key={i} className="h-28 skeleton" />)}
                </div>
                <div className="h-72 skeleton" />
            </div>
        );
    }

    // Build heatmap lookup
    const heatLookup: Record<string, { score: number; count: number }> = {};
    heatmap?.cells.forEach((c) => {
        heatLookup[`${c.source}-${c.hour}`] = { score: c.score, count: c.count };
    });

    const tierBarData = overview
        ? [
            { name: "Critical", count: overview.critical_count, color: TIER_COLORS.critical },
            { name: "High", count: overview.high_count, color: TIER_COLORS.high },
            { name: "Moderate", count: overview.moderate_count, color: TIER_COLORS.moderate },
            { name: "Low", count: overview.low_count, color: TIER_COLORS.low },
        ]
        : [];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">Risk Heatmap</h1>
                <p className="text-sm text-slate-500 mt-1">Cross-signal risk assessment by source and time</p>
            </div>

            {/* Risk KPIs */}
            <div className="grid grid-cols-4 gap-4">
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <Shield className="w-4 h-4 text-indigo-400" />
                        <span className="text-xs text-slate-500 uppercase">Avg Score</span>
                    </div>
                    <p className="text-2xl font-bold text-white">{overview?.average_score.toFixed(3)}</p>
                </div>
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-4 h-4 text-rose-400" />
                        <span className="text-xs text-slate-500 uppercase">Critical</span>
                    </div>
                    <p className="text-2xl font-bold text-rose-400">{overview?.critical_count}</p>
                </div>
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        <span className="text-xs text-slate-500 uppercase">High</span>
                    </div>
                    <p className="text-2xl font-bold text-amber-400">{overview?.high_count}</p>
                </div>
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <TrendingUp className="w-4 h-4 text-emerald-400" />
                        <span className="text-xs text-slate-500 uppercase">Trend</span>
                    </div>
                    <p className="text-2xl font-bold text-emerald-400 capitalize">{overview?.trend}</p>
                </div>
            </div>

            {/* Heatmap Grid */}
            <div className="glass-card p-6">
                <h3 className="text-sm font-semibold text-white mb-5">Source × Hour Risk Map</h3>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr>
                                <th className="text-left text-xs text-slate-500 uppercase tracking-wider py-2 pr-4 w-24">Source</th>
                                {HOURS.map((h) => (
                                    <th key={h} className="text-center text-[0.6rem] text-slate-600 py-2 px-0.5 w-8">
                                        {h.toString().padStart(2, "0")}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {SOURCES.map((source) => (
                                <tr key={source}>
                                    <td className="py-1 pr-4">
                                        <span className={`source-badge source-${source}`}>{source}</span>
                                    </td>
                                    {HOURS.map((h) => {
                                        const cell = heatLookup[`${source}-${h}`];
                                        return (
                                            <td key={h} className="py-1 px-0.5">
                                                <div
                                                    className="w-7 h-7 rounded-md transition-all hover:scale-125 hover:z-10 relative cursor-pointer mx-auto"
                                                    style={{ background: getHeatColor(cell?.score || 0) }}
                                                    title={cell ? `${source} @ ${h}:00 — Score: ${cell.score.toFixed(3)} (${cell.count} signals)` : `No data`}
                                                />
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {/* Legend */}
                <div className="flex items-center gap-4 mt-4 justify-end">
                    {[
                        { label: "Low", color: "rgba(16, 185, 129, 0.25)" },
                        { label: "Moderate", color: "rgba(99, 102, 241, 0.4)" },
                        { label: "High", color: "rgba(245, 158, 11, 0.6)" },
                        { label: "Critical", color: "rgba(244, 63, 94, 0.7)" },
                    ].map((l) => (
                        <div key={l.label} className="flex items-center gap-1.5">
                            <div className="w-3 h-3 rounded" style={{ background: l.color }} />
                            <span className="text-[0.65rem] text-slate-500">{l.label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Tier Distribution + Top Risks */}
            <div className="grid grid-cols-3 gap-5">
                <div className="glass-card p-6">
                    <h3 className="text-sm font-semibold text-white mb-4">Tier Distribution</h3>
                    <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={tierBarData}>
                            <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                            <YAxis tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} width={30} />
                            <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid rgba(99,102,241,0.3)", borderRadius: 10, fontSize: 12 }} />
                            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                                {tierBarData.map((entry) => (
                                    <Cell key={entry.name} fill={entry.color} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                <div className="glass-card p-6 col-span-2">
                    <h3 className="text-sm font-semibold text-white mb-4">Top Risk Signals</h3>
                    <div className="space-y-2 max-h-[230px] overflow-y-auto">
                        {overview?.top_risks.map((r) => (
                            <div key={r.id} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: "rgba(255,255,255,0.02)" }}>
                                <span className={`source-badge source-${r.source}`}>{r.source}</span>
                                <span className="flex-1 text-sm text-slate-300 truncate">{r.title}</span>
                                <span className={`badge badge-${r.risk_tier}`}>{r.risk_score.toFixed(3)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
