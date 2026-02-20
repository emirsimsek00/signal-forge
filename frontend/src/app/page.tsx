"use client";

import { useEffect, useState, useCallback } from "react";
import { api, DashboardOverview, ForecastResponse } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import Link from "next/link";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, ComposedChart,
} from "recharts";
import {
  Radio, AlertTriangle, Shield, TrendingUp, RefreshCw, Zap, Wifi,
  Clock, TrendingDown, Activity,
} from "lucide-react";

const TIER_COLORS: Record<string, string> = {
  critical: "#f43f5e", high: "#f59e0b", moderate: "#6366f1", low: "#10b981",
};
const SOURCE_COLORS: Record<string, string> = {
  reddit: "#ff6b35", news: "#22d3ee", zendesk: "#34d399", stripe: "#14b8a6",
  pagerduty: "#f97316", system: "#a78bfa", financial: "#fbbf24",
};

interface RiskTrendPoint {
  timestamp: string; avg_risk: number; max_risk: number; count: number; high_risk_count: number;
}
interface SentimentDriftPoint {
  timestamp: string; avg_sentiment: number; negative_ratio: number; positive_ratio: number; neutral_ratio: number; total: number;
}
interface IncidentFreqPoint {
  date: string; total: number; critical: number; high: number; medium: number; low: number;
}

const tooltipStyle = {
  background: "#1e293b",
  border: "1px solid rgba(99, 102, 241, 0.3)",
  borderRadius: 10,
  fontSize: 12,
  color: "#f1f5f9",
};

export default function OverviewPage() {
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [riskTrend, setRiskTrend] = useState<RiskTrendPoint[]>([]);
  const [sentimentDrift, setSentimentDrift] = useState<SentimentDriftPoint[]>([]);
  const [incidentFreq, setIncidentFreq] = useState<IncidentFreqPoint[]>([]);
  const [forecastMetric, setForecastMetric] = useState("mrr");
  const [availableMetrics, setAvailableMetrics] = useState<string[]>(["mrr", "churn_rate", "api_latency_ms", "cpu_usage"]);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [overview, forecastResult, riskTrendResult, sentimentResult, incidentResult] =
        await Promise.all([
          api.dashboardOverview(),
          api.forecast(forecastMetric, 8, 168).catch(() => null),
          api.dashboardRiskTrend(72).catch(() => ({ points: [] })),
          api.dashboardSentimentDrift(72).catch(() => ({ points: [] })),
          api.dashboardIncidentFrequency(14).catch(() => ({ points: [] })),
        ]);
      setData(overview);
      setForecast(forecastResult);
      setRiskTrend(riskTrendResult.points);
      setSentimentDrift(sentimentResult.points);
      setIncidentFreq(incidentResult.points);
      setLastFetched(new Date());
    } catch (e) {
      console.error("Failed to fetch dashboard:", e);
    } finally {
      setLoading(false);
    }
  }, [forecastMetric]);

  const { connected, signalCount } = useWebSocket({
    channels: ["signals"],
    onSignal: () => { fetchData(); },
  });

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    api.forecastMetrics(168)
      .then((result) => {
        if (result.metrics.length > 0) {
          setAvailableMetrics(result.metrics);
          if (!result.metrics.includes(forecastMetric)) setForecastMetric(result.metrics[0]);
        }
      })
      .catch(() => { });
  }, [forecastMetric]);

  const handleIngest = async () => {
    setIngesting(true);
    try { await api.triggerIngestion(30); await fetchData(); }
    finally { setIngesting(false); }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 skeleton" />
        <div className="grid grid-cols-4 gap-5">{[...Array(4)].map((_, i) => <div key={i} className="h-32 skeleton" />)}</div>
        <div className="grid grid-cols-2 gap-5"><div className="h-72 skeleton" /><div className="h-72 skeleton" /></div>
      </div>
    );
  }

  const tierData = data ? Object.entries(data.tier_distribution).map(([name, value]) => ({ name, value })) : [];
  const sourceData = data?.source_distribution || [];
  const observed = forecast?.observed_points.slice(-16) || [];
  const predicted = forecast?.predicted_values || [];
  const forecastSeries = [
    ...observed.map((p) => ({ time: new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), observed: p.value, predicted: null as number | null })),
    ...predicted.map((p) => ({ time: new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), observed: null as number | null, predicted: p.value })),
  ];

  // Format time-series for charts
  const riskTrendFormatted = riskTrend.map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    avg: +(p.avg_risk * 100).toFixed(1),
    max: +(p.max_risk * 100).toFixed(1),
    high: p.high_risk_count,
  }));

  const sentimentFormatted = sentimentDrift.map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    sentiment: +(p.avg_sentiment * 100).toFixed(1),
    negative: +(p.negative_ratio * 100).toFixed(0),
    positive: +(p.positive_ratio * 100).toFixed(0),
  }));

  const incidentFormatted = incidentFreq.map((p) => ({
    day: p.date.slice(5),
    ...p,
  }));

  // Data freshness — time since last signal
  const freshness = data?.recent_signals?.[0]?.timestamp
    ? Math.round((Date.now() - new Date(data.recent_signals[0].timestamp).getTime()) / 60000)
    : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Operations Overview</h1>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-sm text-slate-500">Real-time multimodal signal intelligence</p>
            <span className="flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full" style={{
              background: connected ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
              color: connected ? "#10b981" : "#ef4444",
              border: `1px solid ${connected ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)"}`,
            }}>
              <Wifi size={10} />
              {connected ? "Live" : "Offline"}
              {signalCount > 0 && ` · ${signalCount} new`}
            </span>
            {/* Data freshness indicator */}
            {freshness !== null && (
              <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full" style={{
                background: freshness < 10 ? "rgba(16,185,129,0.1)" : freshness < 60 ? "rgba(245,158,11,0.1)" : "rgba(244,63,94,0.1)",
                color: freshness < 10 ? "#10b981" : freshness < 60 ? "#f59e0b" : "#f43f5e",
                border: `1px solid ${freshness < 10 ? "rgba(16,185,129,0.2)" : freshness < 60 ? "rgba(245,158,11,0.2)" : "rgba(244,63,94,0.2)"}`,
              }}>
                <Clock size={10} />
                {freshness < 1 ? "Just now" : freshness < 60 ? `${freshness}m ago` : `${Math.round(freshness / 60)}h ago`}
              </span>
            )}
            {lastFetched && (
              <span className="text-[0.6rem] text-slate-600">
                Updated {lastFetched.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
        <button onClick={handleIngest} disabled={ingesting} className="btn-primary flex items-center gap-2">
          {ingesting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
          {ingesting ? "Ingesting..." : "Ingest Signals"}
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-5">
        <div className="kpi-card">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: "rgba(99, 102, 241, 0.15)" }}>
              <Radio className="w-4 h-4 text-indigo-400" />
            </div>
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Signals</span>
          </div>
          <p className="text-3xl font-bold text-white">{data?.total_signals.toLocaleString()}</p>
          <p className="text-xs text-slate-500 mt-1">Across all sources</p>
        </div>
        <div className="kpi-card">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: "rgba(244, 63, 94, 0.15)" }}>
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            </div>
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Active Incidents</span>
          </div>
          <p className="text-3xl font-bold text-white">{data?.active_incidents}</p>
          <p className="text-xs text-slate-500 mt-1">Requiring attention</p>
        </div>
        <div className="kpi-card">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: "rgba(245, 158, 11, 0.15)" }}>
              <Shield className="w-4 h-4 text-amber-400" />
            </div>
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Avg Risk Score</span>
          </div>
          <p className="text-3xl font-bold text-white">{(data?.avg_risk_score ?? 0).toFixed(2)}</p>
          <p className="text-xs text-slate-500 mt-1">Composite score (0–1)</p>
        </div>
        <div className="kpi-card">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: "rgba(16, 185, 129, 0.15)" }}>
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Sources Active</span>
          </div>
          <p className="text-3xl font-bold text-white">{sourceData.length}</p>
          <p className="text-xs text-slate-500 mt-1">Connected sources</p>
        </div>
      </div>

      {/* Charts Row 1: Signal Volume + Risk Distribution */}
      <div className="grid grid-cols-3 gap-5">
        <div className="glass-card p-6 col-span-2">
          <h3 className="text-sm font-semibold text-white mb-4">Signal Volume (24h)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={data?.signals_per_hour || []}>
              <defs>
                <linearGradient id="signalGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="hour" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} width={30} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={2} fill="url(#signalGradient)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-white mb-4">Risk Distribution</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={tierData} cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={3} dataKey="value">
                {tierData.map((entry) => <Cell key={entry.name} fill={TIER_COLORS[entry.name] || "#6366f1"} stroke="transparent" />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 mt-2 justify-center">
            {tierData.map((t) => (
              <div key={t.name} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: TIER_COLORS[t.name] }} />
                <span className="text-[0.7rem] text-slate-400 capitalize">{t.name} ({t.value})</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Charts Row 2: Risk Trend + Sentiment Drift */}
      <div className="grid grid-cols-2 gap-5">
        <div className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">Risk Trend (72h)</h3>
          </div>
          {riskTrendFormatted.length === 0 ? (
            <div className="text-sm text-slate-500 py-10 text-center">No risk data available yet. Ingest signals to populate.</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={riskTrendFormatted}>
                <defs>
                  <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} width={35} unit="%" />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="avg" stroke="#f59e0b" strokeWidth={2} fill="url(#riskGrad)" name="Avg Risk" />
                <Line type="monotone" dataKey="max" stroke="#f43f5e" strokeWidth={1.5} dot={false} strokeDasharray="3 3" name="Peak Risk" />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingDown className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-white">Sentiment Drift (72h)</h3>
          </div>
          {sentimentFormatted.length === 0 ? (
            <div className="text-sm text-slate-500 py-10 text-center">No sentiment data available yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={sentimentFormatted}>
                <defs>
                  <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} width={35} unit="%" />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="sentiment" stroke="#22d3ee" strokeWidth={2} fill="url(#sentGrad)" name="Avg Sentiment" />
                <Bar dataKey="negative" fill="#f43f5e" opacity={0.5} barSize={8} radius={[2, 2, 0, 0]} name="Negative %" />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Charts Row 3: Incident Frequency + Source Distribution + Recent Signals */}
      <div className="grid grid-cols-3 gap-5">
        <div className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-rose-400" />
            <h3 className="text-sm font-semibold text-white">Incident Frequency</h3>
          </div>
          {incidentFormatted.length === 0 ? (
            <div className="text-sm text-slate-500 py-10 text-center">No incident data yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={incidentFormatted}>
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} width={25} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="critical" stackId="a" fill="#f43f5e" radius={[0, 0, 0, 0]} />
                <Bar dataKey="high" stackId="a" fill="#f59e0b" />
                <Bar dataKey="medium" stackId="a" fill="#6366f1" />
                <Bar dataKey="low" stackId="a" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Source Bar Chart */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-white mb-4">By Source</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={sourceData} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="source" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} width={60} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                {sourceData.map((entry) => <Cell key={entry.source} fill={SOURCE_COLORS[entry.source] || "#6366f1"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Recent Signals Feed */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-white mb-4">Recent Signals</h3>
          <div className="space-y-2 max-h-[230px] overflow-y-auto pr-2">
            {data?.recent_signals.map((signal) => (
              <Link key={signal.id} href={`/signals/${signal.id}`}
                className="flex items-center gap-3 p-2.5 rounded-xl transition-colors hover:bg-white/5"
                style={{ background: "rgba(255,255,255,0.02)" }}>
                <div className={`source-badge source-${signal.source}`}>{signal.source}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-300 truncate">{signal.title}</p>
                </div>
                {signal.risk_tier && <span className={`badge badge-${signal.risk_tier}`}>{signal.risk_tier}</span>}
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Forecast Panel */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Metric Forecast</h3>
            <p className="text-xs text-slate-500 mt-1">
              Projection for the next {forecast?.predicted_values.length ?? 0} intervals
            </p>
          </div>
          <div className="flex items-center gap-3">
            {forecast && (
              <span className="text-[0.65rem] text-slate-500">
                {forecast.method} · {forecast.trend} · {(forecast.confidence * 100).toFixed(0)}% confidence
              </span>
            )}
            <select value={forecastMetric} onChange={(e) => setForecastMetric(e.target.value)}
              className="text-xs rounded-lg px-2.5 py-1.5 border border-white/10 bg-white/5 text-slate-300">
              {availableMetrics.map((metric) => <option key={metric} value={metric}>{metric}</option>)}
            </select>
          </div>
        </div>
        {forecastSeries.length === 0 ? (
          <div className="text-sm text-slate-500 py-10 text-center">No forecast data available for this metric.</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={forecastSeries}>
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} width={40} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="observed" stroke="#22d3ee" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="predicted" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
