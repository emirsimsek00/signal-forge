"use client";

import { useEffect, useState } from "react";
import { api, TimelineEntry } from "@/lib/api";
import { AlertTriangle, Radio, Clock, ChevronDown } from "lucide-react";

const SEVERITY_COLORS: Record<string, string> = {
    critical: "#f43f5e",
    high: "#f59e0b",
    medium: "#6366f1",
    low: "#10b981",
};

export default function IncidentsPage() {
    const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        api.dashboardTimeline(50)
            .then((d) => setTimeline(d.timeline))
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                <div className="space-y-4">
                    {[...Array(6)].map((_, i) => <div key={i} className="h-20 skeleton" />)}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">Incident Timeline</h1>
                <p className="text-sm text-slate-500 mt-1">Chronological view of signals and incidents</p>
            </div>

            {/* Timeline */}
            <div className="relative">
                {/* Vertical line */}
                <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-indigo-500/30 via-violet-500/20 to-transparent" />

                <div className="space-y-4 pl-16">
                    {timeline.map((item, idx) => (
                        <div
                            key={`${item.type}-${item.id}`}
                            className="glass-card p-5 relative"
                            style={{
                                animationDelay: `${idx * 50}ms`,
                            }}
                        >
                            {/* Timeline dot */}
                            <div
                                className="absolute -left-[2.6rem] top-6 w-3 h-3 rounded-full border-2"
                                style={{
                                    background: item.type === "incident"
                                        ? SEVERITY_COLORS[item.severity || "medium"]
                                        : item.risk_tier
                                            ? SEVERITY_COLORS[item.risk_tier === "critical" ? "critical" : item.risk_tier === "high" ? "high" : "low"]
                                            : "#6366f1",
                                    borderColor: "var(--bg-primary)",
                                }}
                            />

                            <div className="flex items-start justify-between">
                                <div className="flex items-start gap-3">
                                    {item.type === "incident" ? (
                                        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                                    ) : (
                                        <Radio className="w-4 h-4 text-indigo-400 mt-0.5 shrink-0" />
                                    )}

                                    <div>
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-slate-500">
                                                {item.type}
                                            </span>
                                            {item.source && (
                                                <span className={`source-badge source-${item.source}`}>{item.source}</span>
                                            )}
                                            {item.severity && (
                                                <span className={`badge badge-${item.severity === "medium" ? "moderate" : item.severity}`}>
                                                    {item.severity}
                                                </span>
                                            )}
                                            {item.risk_tier && (
                                                <span className={`badge badge-${item.risk_tier}`}>{item.risk_tier}</span>
                                            )}
                                        </div>
                                        <p className="text-sm text-slate-300">{item.title}</p>
                                    </div>
                                </div>

                                <div className="flex items-center gap-1.5 text-xs text-slate-500 shrink-0">
                                    <Clock className="w-3 h-3" />
                                    {item.timestamp ? new Date(item.timestamp).toLocaleString() : "—"}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
