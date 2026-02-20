"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Incident } from "@/lib/api";
import Link from "next/link";
import {
    AlertTriangle,
    CheckCircle2,
    RefreshCw,
    RotateCcw,
    SearchX,
    ShieldAlert,
    XCircle,
} from "lucide-react";

type StatusFilter = "open" | "all" | "active" | "investigating" | "resolved" | "dismissed";
type LifecycleAction = "acknowledge" | "resolve" | "dismiss" | "reopen";

const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
    { value: "open", label: "Open" },
    { value: "all", label: "All" },
    { value: "active", label: "Active" },
    { value: "investigating", label: "Investigating" },
    { value: "resolved", label: "Resolved" },
    { value: "dismissed", label: "Dismissed" },
];

const SEVERITY_FILTERS: Array<{ value: string; label: string }> = [
    { value: "all", label: "All severities" },
    { value: "critical", label: "Critical" },
    { value: "high", label: "High" },
    { value: "medium", label: "Medium" },
    { value: "low", label: "Low" },
];

const STATUS_BADGE_CLASS: Record<string, string> = {
    active: "badge-high",
    investigating: "badge-moderate",
    resolved: "badge-low",
    dismissed: "badge-critical",
};

function actionLabel(action: LifecycleAction): string {
    if (action === "acknowledge") return "Acknowledge";
    if (action === "resolve") return "Resolve";
    if (action === "dismiss") return "Dismiss";
    return "Reopen";
}

function actionIcon(action: LifecycleAction) {
    if (action === "acknowledge") return ShieldAlert;
    if (action === "resolve") return CheckCircle2;
    if (action === "dismiss") return XCircle;
    return RotateCcw;
}

function availableActions(status: string): LifecycleAction[] {
    if (status === "active") return ["acknowledge", "resolve", "dismiss"];
    if (status === "investigating") return ["resolve", "dismiss"];
    if (status === "resolved" || status === "dismissed") return ["reopen"];
    return [];
}

function incidentSignalCount(incident: Incident): number {
    if (!incident.related_signal_ids_json) return 0;
    try {
        const ids = JSON.parse(incident.related_signal_ids_json);
        if (Array.isArray(ids)) {
            return ids.length;
        }
        return 0;
    } catch {
        return 0;
    }
}

export default function IncidentsPage() {
    const [incidents, setIncidents] = useState<Incident[]>([]);
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("open");
    const [severityFilter, setSeverityFilter] = useState("all");
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [pendingById, setPendingById] = useState<Record<number, LifecycleAction | null>>({});

    const fetchIncidents = useCallback(async (initialLoad = false) => {
        if (initialLoad) {
            setLoading(true);
        } else {
            setRefreshing(true);
        }
        setError(null);
        try {
            const severity = severityFilter === "all" ? undefined : severityFilter;
            const result = await api.listIncidents(undefined, severity, 200);
            setIncidents(result);
        } catch {
            setError("Failed to load incidents.");
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [severityFilter]);

    useEffect(() => {
        void fetchIncidents(true);
    }, [fetchIncidents]);

    const visibleIncidents = useMemo(() => {
        return incidents.filter((incident) => {
            if (statusFilter === "all") return true;
            if (statusFilter === "open") {
                return incident.status === "active" || incident.status === "investigating";
            }
            return incident.status === statusFilter;
        });
    }, [incidents, statusFilter]);

    const applyAction = useCallback(async (incidentId: number, action: LifecycleAction) => {
        setPendingById((prev) => ({ ...prev, [incidentId]: action }));
        setError(null);
        try {
            let updated: Incident;
            if (action === "acknowledge") {
                updated = await api.acknowledgeIncident(incidentId);
            } else if (action === "resolve") {
                updated = await api.resolveIncident(incidentId);
            } else if (action === "dismiss") {
                updated = await api.dismissIncident(incidentId);
            } else {
                updated = await api.reopenIncident(incidentId);
            }
            setIncidents((prev) =>
                prev.map((incident) => (incident.id === updated.id ? updated : incident))
            );
        } catch {
            setError(`Failed to ${action} incident #${incidentId}.`);
        } finally {
            setPendingById((prev) => ({ ...prev, [incidentId]: null }));
        }
    }, []);

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                <div className="space-y-4">
                    {[...Array(5)].map((_, i) => <div key={i} className="h-36 skeleton" />)}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">Incidents</h1>
                    <p className="text-sm text-slate-500 mt-1">
                        {visibleIncidents.length} shown · {incidents.length} total
                    </p>
                </div>
                <button
                    onClick={() => void fetchIncidents(false)}
                    disabled={refreshing}
                    className="btn-primary flex items-center gap-2"
                >
                    <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
                    {refreshing ? "Refreshing..." : "Refresh"}
                </button>
            </div>

            <div className="glass-card p-4 flex flex-wrap items-center gap-3">
                <label className="text-xs text-slate-400 uppercase tracking-wider">Status</label>
                <select
                    className="bg-slate-900/70 border border-slate-700 text-sm text-slate-200 rounded-lg px-3 py-2"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                >
                    {STATUS_FILTERS.map((option) => (
                        <option key={option.value} value={option.value}>
                            {option.label}
                        </option>
                    ))}
                </select>

                <label className="text-xs text-slate-400 uppercase tracking-wider ml-2">Severity</label>
                <select
                    className="bg-slate-900/70 border border-slate-700 text-sm text-slate-200 rounded-lg px-3 py-2"
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value)}
                >
                    {SEVERITY_FILTERS.map((option) => (
                        <option key={option.value} value={option.value}>
                            {option.label}
                        </option>
                    ))}
                </select>
            </div>

            {error && (
                <div className="glass-card p-4 border-rose-500/30 text-sm text-rose-300">
                    {error}
                </div>
            )}

            {visibleIncidents.length === 0 ? (
                <div className="glass-card p-12 text-center">
                    <div className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center bg-slate-800/70">
                        <SearchX className="w-8 h-8 text-slate-400" />
                    </div>
                    <h3 className="text-lg font-semibold text-white mb-2">No incidents found</h3>
                    <p className="text-sm text-slate-500">
                        Adjust filters or refresh after new ingestion cycles.
                    </p>
                </div>
            ) : (
                <div className="space-y-4">
                    {visibleIncidents.map((incident) => {
                        const pendingAction = pendingById[incident.id];
                        const actions = availableActions(incident.status);
                        const severityClass = incident.severity === "medium"
                            ? "badge-moderate"
                            : `badge-${incident.severity}`;
                        const statusClass = STATUS_BADGE_CLASS[incident.status] || "badge-moderate";
                        const relatedSignals = incidentSignalCount(incident);

                        return (
                            <div key={incident.id} className="glass-card p-5 space-y-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-start gap-3">
                                        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                                        <div>
                                            <p className="text-sm font-semibold text-slate-100 hover:text-indigo-300 transition-colors">
                                                <Link href={`/incidents/${incident.id}`}>{incident.title}</Link>
                                            </p>
                                            <p className="text-sm text-slate-400 mt-1">{incident.description}</p>
                                        </div>
                                    </div>
                                    <div className="text-xs text-slate-500 text-right shrink-0">
                                        <p>#{incident.id}</p>
                                        <p>{new Date(incident.start_time).toLocaleString()}</p>
                                    </div>
                                </div>

                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`badge ${severityClass}`}>{incident.severity}</span>
                                    <span className={`badge ${statusClass}`}>{incident.status}</span>
                                    <span className="text-xs text-slate-500">
                                        {relatedSignals} related signal{relatedSignals === 1 ? "" : "s"}
                                    </span>
                                    {incident.end_time && (
                                        <span className="text-xs text-slate-500">
                                            Closed: {new Date(incident.end_time).toLocaleString()}
                                        </span>
                                    )}
                                </div>

                                {incident.root_cause_hypothesis && (
                                    <p className="text-xs text-indigo-300/70">
                                        Hypothesis: {incident.root_cause_hypothesis}
                                    </p>
                                )}

                                {actions.length > 0 && (
                                    <div className="flex flex-wrap items-center gap-2 pt-1">
                                        {actions.map((action) => {
                                            const Icon = actionIcon(action);
                                            const isPending = pendingAction === action;
                                            return (
                                                <button
                                                    key={action}
                                                    onClick={() => void applyAction(incident.id, action)}
                                                    disabled={Boolean(pendingAction)}
                                                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-indigo-400/50 hover:text-indigo-300 disabled:opacity-50 disabled:cursor-not-allowed transition"
                                                >
                                                    <Icon className={`w-3.5 h-3.5 ${isPending ? "animate-spin" : ""}`} />
                                                    {isPending ? `${actionLabel(action)}...` : actionLabel(action)}
                                                </button>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
