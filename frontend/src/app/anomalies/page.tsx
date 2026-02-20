"use client";

import { useEffect, useState, useCallback } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
    AlertTriangle, Activity, TrendingUp, Frown, RefreshCw,
    Shield, Clock,
} from "lucide-react";

interface AnomalyEvent {
    id: string;
    type: string;
    severity: string;
    title: string;
    description: string;
    affected_source: string | null;
    metric_value: number;
    threshold: number;
    affected_signal_ids: number[];
    detected_at: string;
}

interface AnomalyStatus {
    total_events: number;
    severity_breakdown: Record<string, number>;
    type_breakdown: Record<string, number>;
    status: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TYPE_CONFIG: Record<string, { icon: typeof Activity; color: string; label: string }> = {
    volume_spike: { icon: TrendingUp, color: "#6366f1", label: "Volume Spike" },
    risk_spike: { icon: Shield, color: "#f43f5e", label: "Risk Surge" },
    sentiment_drift: { icon: Frown, color: "#f59e0b", label: "Sentiment Drift" },
};

const SEVERITY_STYLE: Record<string, { bg: string; text: string; border: string }> = {
    critical: { bg: "rgba(244, 63, 94, 0.12)", text: "#f43f5e", border: "rgba(244, 63, 94, 0.25)" },
    high: { bg: "rgba(245, 158, 11, 0.12)", text: "#f59e0b", border: "rgba(245, 158, 11, 0.25)" },
    moderate: { bg: "rgba(99, 102, 241, 0.12)", text: "#6366f1", border: "rgba(99, 102, 241, 0.25)" },
};

export default function AnomaliesPage() {
    const [events, setEvents] = useState<AnomalyEvent[]>([]);
    const [status, setStatus] = useState<AnomalyStatus | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [evtsRes, statusRes] = await Promise.all([
                fetch(`${API}/api/anomaly/recent`).then((r) => r.json()),
                fetch(`${API}/api/anomaly/status`).then((r) => r.json()),
            ]);
            setEvents(evtsRes.events || []);
            setStatus(statusRes);
        } catch (e) {
            console.error("Failed to fetch anomalies:", e);
        } finally {
            setLoading(false);
        }
    }, []);

    // Auto-refresh on WebSocket anomaly alerts
    useWebSocket({
        channels: ["alerts"],
        onAlert: (data) => {
            if (data.type === "anomaly") {
                fetchData();
            }
        },
    });

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                <div className="grid grid-cols-3 gap-5">
                    {[...Array(3)].map((_, i) => (
                        <div key={i} className="h-28 skeleton" />
                    ))}
                </div>
                <div className="h-96 skeleton" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">Anomaly Detection</h1>
                    <p className="text-sm text-slate-500 mt-1">Statistical anomaly detection across signal patterns</p>
                </div>
                <button onClick={fetchData} className="btn-primary flex items-center gap-2">
                    <RefreshCw className="w-4 h-4" />
                    Refresh
                </button>
            </div>

            {/* Status Cards */}
            <div className="grid grid-cols-3 gap-5">
                {Object.entries(TYPE_CONFIG).map(([type, cfg]) => {
                    const Icon = cfg.icon;
                    const count = status?.type_breakdown[type] || 0;
                    return (
                        <div key={type} className="kpi-card">
                            <div className="flex items-center gap-3 mb-3">
                                <div
                                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                                    style={{ background: `${cfg.color}20` }}
                                >
                                    <Icon className="w-4 h-4" style={{ color: cfg.color }} />
                                </div>
                                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                                    {cfg.label}
                                </span>
                            </div>
                            <p className="text-3xl font-bold text-white">{count}</p>
                            <p className="text-xs text-slate-500 mt-1">events detected</p>
                        </div>
                    );
                })}
            </div>

            {/* Events Timeline */}
            <div className="glass-card p-6">
                <h3 className="text-sm font-semibold text-white mb-4">Event Timeline</h3>
                {events.length === 0 ? (
                    <div className="text-center py-12">
                        <Activity className="w-10 h-10 text-slate-700 mx-auto mb-3" />
                        <p className="text-sm text-slate-500">No anomalies detected yet</p>
                        <p className="text-xs text-slate-600 mt-1">
                            Anomalies are detected after each ingestion cycle
                        </p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {events.map((evt) => {
                            const typeCfg = TYPE_CONFIG[evt.type] || TYPE_CONFIG.volume_spike;
                            const sevStyle = SEVERITY_STYLE[evt.severity] || SEVERITY_STYLE.moderate;
                            const Icon = typeCfg.icon;
                            const time = new Date(evt.detected_at).toLocaleString([], {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                            });
                            return (
                                <div
                                    key={evt.id}
                                    className="flex items-start gap-4 p-4 rounded-xl transition-colors"
                                    style={{
                                        background: sevStyle.bg,
                                        border: `1px solid ${sevStyle.border}`,
                                    }}
                                >
                                    <div
                                        className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                                        style={{ background: `${typeCfg.color}25` }}
                                    >
                                        <Icon className="w-4 h-4" style={{ color: typeCfg.color }} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h4 className="text-sm font-semibold text-white">{evt.title}</h4>
                                            <span
                                                className="text-[0.6rem] uppercase tracking-widest font-semibold px-2 py-0.5 rounded-full"
                                                style={{ color: sevStyle.text, background: `${sevStyle.text}15` }}
                                            >
                                                {evt.severity}
                                            </span>
                                        </div>
                                        <p className="text-xs text-slate-400 leading-relaxed">{evt.description}</p>
                                        {evt.affected_signal_ids.length > 0 && (
                                            <p className="text-[0.65rem] text-slate-600 mt-1.5">
                                                Affected signals: {evt.affected_signal_ids.slice(0, 5).map((id) => `#${id}`).join(", ")}
                                                {evt.affected_signal_ids.length > 5 && ` +${evt.affected_signal_ids.length - 5} more`}
                                            </p>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-1.5 text-[0.65rem] text-slate-600 flex-shrink-0">
                                        <Clock size={10} />
                                        {time}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
