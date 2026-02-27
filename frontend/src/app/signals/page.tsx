"use client";

import { useEffect, useState } from "react";
import { api, Signal, SignalListResponse } from "@/lib/api";
import { Filter, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import Link from "next/link";

const SOURCES = ["all", "reddit", "news", "zendesk", "stripe", "pagerduty", "system", "financial"];
const RISK_TIERS = ["all", "critical", "high", "moderate", "low"];

export default function SignalsPage() {
    const [data, setData] = useState<SignalListResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [sourceFilter, setSourceFilter] = useState("all");
    const [riskFilter, setRiskFilter] = useState("all");
    const [selected, setSelected] = useState<Signal | null>(null);

    useEffect(() => {
        api
            .listSignals(
                page, 15,
                sourceFilter === "all" ? undefined : sourceFilter,
                riskFilter === "all" ? undefined : riskFilter,
            )
            .then(setData)
            .finally(() => setLoading(false));
    }, [page, sourceFilter, riskFilter]);

    const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight">Signal Explorer</h1>
                <p className="text-sm text-slate-500 mt-1">Browse and filter all ingested signals</p>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-slate-500" />
                    <span className="text-xs text-slate-500 uppercase tracking-wider">Source:</span>
                    <div className="flex gap-1">
                        {SOURCES.map((s) => (
                            <button
                                key={s}
                                onClick={() => { setSourceFilter(s); setPage(1); }}
                                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${sourceFilter === s
                                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                                    : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                                    }`}
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex items-center gap-2 ml-4">
                    <span className="text-xs text-slate-500 uppercase tracking-wider">Risk:</span>
                    <div className="flex gap-1">
                        {RISK_TIERS.map((t) => (
                            <button
                                key={t}
                                onClick={() => { setRiskFilter(t); setPage(1); }}
                                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${riskFilter === t
                                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                                    : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                                    }`}
                            >
                                {t}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Table */}
            <div className="glass-card overflow-hidden">
                {loading ? (
                    <div className="p-8 space-y-3">
                        {[...Array(8)].map((_, i) => (
                            <div key={i} className="h-12 skeleton" />
                        ))}
                    </div>
                ) : (
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Source</th>
                                <th>Title</th>
                                <th>Sentiment</th>
                                <th>Risk</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data?.signals.map((signal) => (
                                <tr
                                    key={signal.id}
                                    onClick={() => setSelected(signal)}
                                    className="cursor-pointer hover:bg-indigo-500/5 transition-colors"
                                >
                                    <td>
                                        <span className={`source-badge source-${signal.source}`}>
                                            {signal.source}
                                        </span>
                                    </td>
                                    <td>
                                        <span className="text-slate-300 line-clamp-1">
                                            {signal.title || signal.content.slice(0, 60)}
                                        </span>
                                    </td>
                                    <td>
                                        <span className="flex items-center gap-1.5">
                                            <span>
                                                {signal.sentiment_label === "negative" ? "😟" : signal.sentiment_label === "positive" ? "😊" : "😐"}
                                            </span>
                                            <span className="text-xs text-slate-500">
                                                {signal.sentiment_score !== null ? signal.sentiment_score.toFixed(2) : "—"}
                                            </span>
                                        </span>
                                    </td>
                                    <td>
                                        {signal.risk_tier ? (
                                            <span className={`badge badge-${signal.risk_tier}`}>
                                                {signal.risk_tier}
                                            </span>
                                        ) : (
                                            <span className="text-slate-600">—</span>
                                        )}
                                    </td>
                                    <td className="text-xs text-slate-500">
                                        {new Date(signal.timestamp).toLocaleString()}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}

                {/* Pagination */}
                <div className="flex items-center justify-between px-4 py-3 border-t border-white/5">
                    <span className="text-xs text-slate-500">
                        Page {page} of {totalPages} · {data?.total ?? 0} signals
                    </span>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="p-1.5 rounded-lg text-slate-500 hover:bg-white/5 disabled:opacity-30"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="p-1.5 rounded-lg text-slate-500 hover:bg-white/5 disabled:opacity-30"
                        >
                            <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>

            {/* Signal Detail Modal */}
            {selected && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                    onClick={() => setSelected(null)}
                >
                    <div
                        className="glass-card p-8 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto"
                        onClick={(e) => e.stopPropagation()}
                        style={{ border: "1px solid rgba(99, 102, 241, 0.2)" }}
                    >
                        <div className="flex items-start justify-between mb-4">
                            <div>
                                <span className={`source-badge source-${selected.source} mb-2`}>
                                    {selected.source}
                                </span>
                                <h2 className="text-lg font-bold text-white mt-2">
                                    {selected.title || "Signal Detail"}
                                </h2>
                            </div>
                            {selected.risk_tier && (
                                <span className={`badge badge-${selected.risk_tier}`}>
                                    {selected.risk_tier} · {selected.risk_score?.toFixed(3)}
                                </span>
                            )}
                        </div>

                        <p className="text-sm text-slate-300 leading-relaxed mb-4">{selected.content}</p>

                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <span className="text-xs text-slate-500 uppercase">Sentiment</span>
                                <p className="text-slate-300 mt-1">
                                    {selected.sentiment_label} ({selected.sentiment_score?.toFixed(3)})
                                </p>
                            </div>
                            <div>
                                <span className="text-xs text-slate-500 uppercase">Timestamp</span>
                                <p className="text-slate-300 mt-1">
                                    {new Date(selected.timestamp).toLocaleString()}
                                </p>
                            </div>
                            {selected.summary && (
                                <div className="col-span-2">
                                    <span className="text-xs text-slate-500 uppercase">AI Summary</span>
                                    <p className="text-slate-300 mt-1">{selected.summary}</p>
                                </div>
                            )}
                        </div>

                        <div className="mt-6 flex gap-3">
                            <Link
                                href={`/signals/${selected.id}`}
                                className="btn-primary flex-1 text-center inline-flex items-center justify-center gap-2"
                            >
                                <ExternalLink className="w-4 h-4" /> View Full Analysis
                            </Link>
                            <button
                                onClick={() => setSelected(null)}
                                className="flex-1 rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm text-slate-300 hover:border-indigo-400/50 transition"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
