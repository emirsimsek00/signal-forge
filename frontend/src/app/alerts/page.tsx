"use client";

import { useEffect, useState } from "react";
import { api, Signal } from "@/lib/api";
import { Check, X, AlertTriangle, Clock } from "lucide-react";

export default function AlertsPage() {
    const [alerts, setAlerts] = useState<Signal[]>([]);
    const [loading, setLoading] = useState(true);
    const [dismissed, setDismissed] = useState<Set<number>>(new Set());

    useEffect(() => {
        // Alerts are high/critical risk signals
        Promise.all([
            api.listSignals(1, 50, undefined, "critical"),
            api.listSignals(1, 50, undefined, "high"),
        ])
            .then(([critical, high]) => {
                const all = [...critical.signals, ...high.signals];
                all.sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0));
                setAlerts(all);
            })
            .finally(() => setLoading(false));
    }, []);

    const dismiss = (id: number) => {
        setDismissed((prev) => new Set([...prev, id]));
    };

    const activeAlerts = alerts.filter((a) => !dismissed.has(a.id));

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-48 skeleton" />
                <div className="space-y-3">
                    {[...Array(5)].map((_, i) => <div key={i} className="h-20 skeleton" />)}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">Alert Center</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        {activeAlerts.length} active alerts · {dismissed.size} dismissed
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="pulse-dot" style={{ background: activeAlerts.length > 0 ? "var(--accent-rose)" : "var(--accent-emerald)" }} />
                    <span className="text-xs font-medium" style={{ color: activeAlerts.length > 0 ? "var(--accent-rose)" : "var(--accent-emerald)" }}>
                        {activeAlerts.length > 0 ? "Alerts Active" : "All Clear"}
                    </span>
                </div>
            </div>

            {activeAlerts.length === 0 ? (
                <div className="glass-card p-12 text-center">
                    <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center" style={{ background: "rgba(16, 185, 129, 0.1)" }}>
                        <Check className="w-8 h-8 text-emerald-400" />
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">No Active Alerts</h3>
                    <p className="text-sm text-slate-500">All risk signals are below alert thresholds.</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {activeAlerts.map((alert) => (
                        <div
                            key={alert.id}
                            className="glass-card p-5 flex items-start gap-4"
                            style={{
                                borderLeft: `3px solid ${alert.risk_tier === "critical" ? "#f43f5e" : "#f59e0b"}`,
                            }}
                        >
                            <div
                                className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 mt-0.5"
                                style={{
                                    background: alert.risk_tier === "critical" ? "rgba(244, 63, 94, 0.15)" : "rgba(245, 158, 11, 0.15)",
                                }}
                            >
                                <AlertTriangle
                                    className="w-5 h-5"
                                    style={{ color: alert.risk_tier === "critical" ? "#fb7185" : "#fbbf24" }}
                                />
                            </div>

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className={`badge badge-${alert.risk_tier}`}>{alert.risk_tier}</span>
                                    <span className={`source-badge source-${alert.source}`}>{alert.source}</span>
                                    <span className="text-xs text-slate-500 ml-auto flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {new Date(alert.timestamp).toLocaleString()}
                                    </span>
                                </div>
                                <p className="text-sm font-medium text-slate-200 mb-1">
                                    {alert.title || alert.content.slice(0, 80)}
                                </p>
                                <p className="text-xs text-slate-500 line-clamp-2">{alert.content}</p>
                                {alert.summary && (
                                    <p className="text-xs text-indigo-300/70 mt-1 italic">{alert.summary}</p>
                                )}
                            </div>

                            <div className="flex flex-col gap-2 shrink-0">
                                <button
                                    onClick={() => dismiss(alert.id)}
                                    className="p-2 rounded-lg text-slate-500 hover:bg-white/5 hover:text-slate-300 transition"
                                    title="Dismiss"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                                <span className="text-xs text-center font-mono text-slate-500">
                                    {alert.risk_score?.toFixed(2)}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
