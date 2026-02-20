"use client";

import { useEffect, useState, use, useCallback } from "react";
import { api, IncidentTimeline, Note } from "@/lib/api";
import Link from "next/link";
import {
    ArrowLeft, AlertTriangle, CheckCircle2, XCircle, RotateCcw,
    ShieldAlert, Send, Clock, Radio, MessageSquare, Loader2, FileText,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
    active: "#f59e0b", investigating: "#6366f1", resolved: "#10b981", dismissed: "#64748b",
};

const TIMELINE_ICONS: Record<string, typeof AlertTriangle> = {
    incident_created: AlertTriangle, signal: Radio,
    note: MessageSquare, incident_resolved: CheckCircle2,
};

type LifecycleAction = "acknowledge" | "resolve" | "dismiss" | "reopen";

function availableActions(status: string): LifecycleAction[] {
    if (status === "active") return ["acknowledge", "resolve", "dismiss"];
    if (status === "investigating") return ["resolve", "dismiss"];
    if (status === "resolved" || status === "dismissed") return ["reopen"];
    return [];
}

export default function IncidentWorkspacePage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const incidentId = Number(id);
    const [data, setData] = useState<IncidentTimeline | null>(null);
    const [notes, setNotes] = useState<Note[]>([]);
    const [noteText, setNoteText] = useState("");
    const [loading, setLoading] = useState(true);
    const [sending, setSending] = useState(false);
    const [actionPending, setActionPending] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            const [timeline, notesList] = await Promise.all([
                api.getIncidentTimeline(incidentId),
                api.getIncidentNotes(incidentId),
            ]);
            setData(timeline);
            setNotes(notesList);
        } catch (e) { console.error(e); }
        finally { setLoading(false); }
    }, [incidentId]);

    useEffect(() => { void load(); }, [load]);

    const sendNote = async () => {
        if (!noteText.trim()) return;
        setSending(true);
        try {
            const note = await api.addIncidentNote(incidentId, noteText.trim());
            setNotes((prev) => [...prev, note]);
            setNoteText("");
            void load(); // refresh timeline
        } catch (e) { console.error(e); }
        finally { setSending(false); }
    };

    const applyAction = async (action: LifecycleAction) => {
        setActionPending(action);
        try {
            if (action === "acknowledge") await api.acknowledgeIncident(incidentId);
            else if (action === "resolve") await api.resolveIncident(incidentId);
            else if (action === "dismiss") await api.dismissIncident(incidentId);
            else await api.reopenIncident(incidentId);
            void load();
        } catch (e) { console.error(e); }
        finally { setActionPending(null); }
    };

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="h-10 w-64 skeleton" />
                <div className="h-48 skeleton" />
                <div className="space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="h-16 skeleton" />)}</div>
            </div>
        );
    }
    if (!data) return <div className="glass-card p-12 text-center text-slate-400">Incident not found</div>;

    const { incident, timeline } = data;
    const actions = availableActions(incident.status);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Link href="/incidents" className="p-2 rounded-lg hover:bg-white/5 transition">
                    <ArrowLeft className="w-5 h-5 text-slate-400" />
                </Link>
                <div className="flex-1">
                    <div className="flex items-center gap-3">
                        <h1 className="text-xl font-bold text-white tracking-tight">{incident.title}</h1>
                        <span className="text-xs text-slate-500">#{incident.id}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                        <span className={`badge badge-${incident.severity === "medium" ? "moderate" : incident.severity}`}>
                            {incident.severity}
                        </span>
                        <span className="badge" style={{ background: `${STATUS_COLORS[incident.status]}20`, color: STATUS_COLORS[incident.status], border: `1px solid ${STATUS_COLORS[incident.status]}40` }}>
                            {incident.status}
                        </span>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {actions.map((action) => {
                        const icons: Record<string, typeof CheckCircle2> = { acknowledge: ShieldAlert, resolve: CheckCircle2, dismiss: XCircle, reopen: RotateCcw };
                        const Icon = icons[action];
                        return (
                            <button key={action} onClick={() => applyAction(action)} disabled={!!actionPending}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs font-medium text-slate-200 hover:border-indigo-400/50 hover:text-indigo-300 disabled:opacity-50 transition">
                                <Icon className={`w-3.5 h-3.5 ${actionPending === action ? "animate-spin" : ""}`} />
                                {action.charAt(0).toUpperCase() + action.slice(1)}
                            </button>
                        );
                    })}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left: Timeline + Notes */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Description */}
                    <div className="glass-card p-5">
                        <p className="text-sm text-slate-300 leading-relaxed">{incident.description}</p>
                    </div>

                    {/* Timeline */}
                    <div className="glass-card p-5">
                        <div className="flex items-center gap-2 mb-4">
                            <Clock className="w-4 h-4 text-indigo-400" />
                            <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Timeline</h3>
                            <span className="text-xs text-slate-500">{timeline.length} events</span>
                        </div>
                        <div className="space-y-0">
                            {timeline.map((ev, i) => {
                                const Icon = TIMELINE_ICONS[ev.type] || Radio;
                                const color = ev.type === "signal" ? "#06b6d4" : ev.type === "note" ? "#8b5cf6" : ev.type === "incident_resolved" ? "#10b981" : "#f59e0b";
                                return (
                                    <div key={i} className="flex gap-3 relative">
                                        {i < timeline.length - 1 && (
                                            <div className="absolute left-[11px] top-8 bottom-0 w-px" style={{ background: "rgba(255,255,255,0.06)" }} />
                                        )}
                                        <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                                            style={{ background: `${color}20`, border: `1px solid ${color}40` }}>
                                            <Icon className="w-3 h-3" style={{ color }} />
                                        </div>
                                        <div className="flex-1 pb-4">
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-slate-500">{new Date(ev.timestamp).toLocaleString()}</span>
                                                {ev.source && <span className={`source-badge source-${ev.source}`}>{ev.source}</span>}
                                                {ev.risk_tier && <span className={`badge badge-${ev.risk_tier}`}>{ev.risk_tier}</span>}
                                                {ev.author && <span className="text-xs text-violet-400">{ev.author}</span>}
                                            </div>
                                            <p className="text-sm text-slate-300 mt-1">
                                                {ev.signal_id ? (
                                                    <Link href={`/signals/${ev.signal_id}`} className="hover:text-indigo-300 transition">
                                                        {ev.content}
                                                    </Link>
                                                ) : ev.content}
                                            </p>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Notes */}
                    <div className="glass-card p-5">
                        <div className="flex items-center gap-2 mb-4">
                            <MessageSquare className="w-4 h-4 text-violet-400" />
                            <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Notes</h3>
                        </div>
                        {notes.length > 0 && (
                            <div className="space-y-3 mb-4">
                                {notes.map((note) => (
                                    <div key={note.id} className="px-4 py-3 rounded-xl" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-xs font-medium text-violet-400">{note.author}</span>
                                            <span className="text-xs text-slate-600">{new Date(note.created_at).toLocaleString()}</span>
                                        </div>
                                        <p className="text-sm text-slate-300">{note.content}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                        <div className="flex gap-2">
                            <input type="text" value={noteText}
                                onChange={(e) => setNoteText(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && sendNote()}
                                placeholder="Add a note..."
                                className="flex-1 bg-slate-900/70 border border-slate-700 text-sm text-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500" />
                            <button onClick={sendNote} disabled={sending || !noteText.trim()}
                                className="btn-primary px-4 disabled:opacity-50">
                                {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right: Root Cause + Actions */}
                <div className="space-y-6">
                    {incident.root_cause_hypothesis && (
                        <div className="glass-card p-5">
                            <div className="flex items-center gap-2 mb-3">
                                <AlertTriangle className="w-4 h-4 text-amber-400" />
                                <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Root Cause</h3>
                            </div>
                            <p className="text-sm text-slate-300 leading-relaxed">{incident.root_cause_hypothesis}</p>
                        </div>
                    )}

                    {incident.recommended_actions && (
                        <div className="glass-card p-5">
                            <div className="flex items-center gap-2 mb-3">
                                <FileText className="w-4 h-4 text-emerald-400" />
                                <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Actions</h3>
                            </div>
                            <div className="space-y-2">
                                {incident.recommended_actions.split("\n").filter(Boolean).map((line, i) => (
                                    <div key={i} className="flex items-start gap-2">
                                        <span className="text-xs text-emerald-400 mt-0.5 shrink-0">{i + 1}.</span>
                                        <span className="text-sm text-slate-300">{line.replace(/^\d+\.\s*/, "")}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
