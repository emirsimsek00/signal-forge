"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import {
    Activity, CheckCircle2, AlertCircle, Clock, RefreshCw, Wifi, WifiOff,
    Database, Cpu, Server,
} from "lucide-react";

interface HealthData {
    status: string;
    version: string;
    websocket_connections: number;
    scheduler_active: boolean;
}

export default function HealthPage() {
    const [health, setHealth] = useState<HealthData | null>(null);
    const [overview, setOverview] = useState<{ total: number; sources: string[] } | null>(null);
    const [loading, setLoading] = useState(true);
    const [lastChecked, setLastChecked] = useState<Date | null>(null);
    const [refreshing, setRefreshing] = useState(false);

    const fetchHealth = useCallback(async (initial = false) => {
        if (initial) setLoading(true);
        else setRefreshing(true);
        try {
            const [h, o] = await Promise.all([
                api.health(),
                api.dashboardOverview().then((d) => ({
                    total: d.total_signals,
                    sources: d.source_distribution.map((s) => s.source),
                })),
            ]);
            setHealth(h);
            setOverview(o);
            setLastChecked(new Date());
        } catch (e) { console.error(e); }
        finally { setLoading(false); setRefreshing(false); }
    }, []);

    useEffect(() => { void fetchHealth(true); }, [fetchHealth]);

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                <div className="grid grid-cols-2 gap-4">{[...Array(4)].map((_, i) => <div key={i} className="h-32 skeleton" />)}</div>
            </div>
        );
    }

    const isHealthy = health?.status === "healthy";

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">System Health</h1>
                    <p className="text-sm text-slate-500 mt-1">Monitoring and operational status</p>
                </div>
                <button onClick={() => fetchHealth(false)} disabled={refreshing}
                    className="btn-primary flex items-center gap-2">
                    <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
                    Refresh
                </button>
            </div>

            {/* Status banner */}
            <div className="glass-card p-4 flex items-center gap-3"
                style={{ borderColor: isHealthy ? "rgba(16,185,129,0.3)" : "rgba(244,63,94,0.3)" }}>
                {isHealthy ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                ) : (
                    <AlertCircle className="w-5 h-5 text-rose-400" />
                )}
                <div>
                    <span className="text-sm font-medium text-white">
                        {isHealthy ? "All systems operational" : "System degraded"}
                    </span>
                    {lastChecked && (
                        <span className="text-xs text-slate-500 ml-2">
                            Last checked: {lastChecked.toLocaleTimeString()}
                        </span>
                    )}
                </div>
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <Server className="w-4 h-4 text-indigo-400" />
                        <span className="text-xs text-slate-400 uppercase tracking-wider">API</span>
                    </div>
                    <p className="text-xl font-bold" style={{ color: isHealthy ? "#10b981" : "#f43f5e" }}>
                        {isHealthy ? "Online" : "Offline"}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">v{health?.version || "?"}</p>
                </div>

                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <Cpu className="w-4 h-4 text-violet-400" />
                        <span className="text-xs text-slate-400 uppercase tracking-wider">Scheduler</span>
                    </div>
                    <p className="text-xl font-bold" style={{ color: health?.scheduler_active ? "#10b981" : "#f59e0b" }}>
                        {health?.scheduler_active ? "Running" : "Stopped"}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">Background ingestion</p>
                </div>

                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        {(health?.websocket_connections || 0) > 0 ? <Wifi className="w-4 h-4 text-cyan-400" /> : <WifiOff className="w-4 h-4 text-slate-500" />}
                        <span className="text-xs text-slate-400 uppercase tracking-wider">WebSocket</span>
                    </div>
                    <p className="text-xl font-bold text-white">{health?.websocket_connections || 0}</p>
                    <p className="text-xs text-slate-500 mt-1">Active connections</p>
                </div>

                <div className="kpi-card">
                    <div className="flex items-center gap-2 mb-2">
                        <Database className="w-4 h-4 text-emerald-400" />
                        <span className="text-xs text-slate-400 uppercase tracking-wider">Signals</span>
                    </div>
                    <p className="text-xl font-bold text-white">{overview?.total || 0}</p>
                    <p className="text-xs text-slate-500 mt-1">Total indexed</p>
                </div>
            </div>

            {/* Source connectivity */}
            <div className="glass-card p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Activity className="w-4 h-4 text-indigo-400" />
                    <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Data Sources</h3>
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    {["reddit", "news", "zendesk", "stripe", "pagerduty", "system", "financial"].map((src) => {
                        const active = overview?.sources.includes(src);
                        return (
                            <div key={src} className="flex items-center gap-3 px-4 py-3 rounded-xl"
                                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                                <div className="w-2 h-2 rounded-full" style={{ background: active ? "#10b981" : "#64748b" }} />
                                <span className={`source-badge source-${src}`}>{src}</span>
                                <span className="text-xs ml-auto" style={{ color: active ? "#10b981" : "#64748b" }}>
                                    {active ? "Active" : "No data"}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Uptime indicator */}
            <div className="glass-card p-4 flex items-center gap-3">
                <Clock className="w-4 h-4 text-slate-500" />
                <span className="text-xs text-slate-500">
                    Data freshness depends on ingestion interval. Signals are processed every{" "}
                    <span className="text-slate-400 font-mono">60s</span> by default.
                </span>
            </div>
        </div>
    );
}
