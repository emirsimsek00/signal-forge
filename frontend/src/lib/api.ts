const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Signal {
  id: number;
  source: string;
  source_id: string | null;
  title: string | null;
  content: string;
  timestamp: string;
  sentiment_score: number | null;
  sentiment_label: string | null;
  urgency: string | null;
  entities_json: string | null;
  summary: string | null;
  risk_score: number | null;
  risk_tier: string | null;
  created_at: string;
}

export interface SignalListResponse {
  signals: Signal[];
  total: number;
  page: number;
  page_size: number;
}

export interface Incident {
  id: number;
  title: string;
  description: string;
  severity: string;
  status: string;
  start_time: string;
  end_time: string | null;
  related_signal_ids_json: string | null;
  root_cause_hypothesis: string | null;
  recommended_actions: string | null;
  created_at: string;
}

export interface DashboardOverview {
  total_signals: number;
  active_incidents: number;
  avg_risk_score: number;
  tier_distribution: Record<string, number>;
  source_distribution: { source: string; count: number }[];
  recent_signals: {
    id: number;
    source: string;
    title: string;
    risk_score: number | null;
    risk_tier: string | null;
    sentiment_label: string | null;
    timestamp: string;
  }[];
  signals_per_hour: { hour: string; count: number }[];
}

export interface RiskOverview {
  average_score: number;
  critical_count: number;
  high_count: number;
  moderate_count: number;
  low_count: number;
  total_signals: number;
  trend: string;
  top_risks: {
    id: number;
    source: string;
    title: string;
    risk_score: number;
    risk_tier: string;
    sentiment_label: string | null;
    timestamp: string;
  }[];
}

export interface HeatmapData {
  cells: {
    source: string;
    hour: number;
    score: number;
    tier: string;
    count: number;
  }[];
}

export interface TimelineEntry {
  type: "signal" | "incident";
  id: number;
  title: string;
  source?: string;
  severity?: string;
  status?: string;
  risk_tier?: string;
  risk_score?: number;
  timestamp: string;
}

export interface CorrelationResult {
  related_signal_id: number;
  score: number;
  method: string;
  explanation: string;
}

export interface GraphNode {
  id: number;
  source: string;
  title: string;
  risk_score: number;
  risk_tier: string;
  sentiment_label: string;
  timestamp: string;
}

export interface GraphEdge {
  source: number;
  target: number;
  weight: number;
  method: string;
  explanation: string;
}

export interface CorrelationGraphData {
  center_signal_id: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
}

export interface ChatCitedSignal {
  id: number;
  source: string;
  title: string | null;
  risk_tier: string | null;
  sentiment_label: string | null;
  snippet: string;
}

export interface ChatResponse {
  answer: string;
  intent: string;
  cited_signals: ChatCitedSignal[];
  signal_count: number;
  llm_powered?: boolean;
}

export interface ExecutiveBrief {
  generated_at: string;
  tone: "executive_concise" | "technical_detailed" | "customer_facing";
  lookback_hours: number;
  situation_overview: string;
  key_risk_indicators: string[];
  root_cause_hypotheses: string[];
  recommended_actions: string[];
  confidence_score: number;
  supporting_metrics: {
    total_signals: number;
    avg_risk_score: number;
    tier_distribution: Record<string, number>;
    negative_sentiment_ratio: number;
    active_incidents: number;
    source_distribution: { source: string; count: number }[];
  };
  top_risk_signals: {
    id: number;
    source: string;
    title: string;
    risk_score: number;
    risk_tier: string;
  }[];
}

export interface ForecastPoint {
  timestamp: string;
  value: number;
}

export interface ForecastResponse {
  metric_name: string;
  method: string;
  trend: string;
  confidence: number;
  generated_at: string;
  observed_points: ForecastPoint[];
  predicted_values: ForecastPoint[];
}

// ── v2 Types ────────────────────────────────────────────

export interface RiskComponent {
  score: number;
  weight: number;
  weighted: number;
}

export interface SignalExplanation {
  signal: Signal;
  risk_explanation: {
    composite_score: number | null;
    tier: string | null;
    explanation: string;
    components: Record<string, RiskComponent>;
    weights: Record<string, number>;
  };
  entities: { text: string; label: string }[];
  similar_signals: {
    id: number;
    title: string | null;
    source: string;
    risk_tier: string | null;
    risk_score: number | null;
    similarity: number;
    timestamp: string | null;
  }[];
}

export interface Note {
  id: number;
  incident_id: number;
  content: string;
  author: string;
  created_at: string;
}

export interface TimelineEvent {
  type: string;
  timestamp: string;
  content: string;
  source?: string;
  signal_id?: number;
  risk_tier?: string;
  sentiment_label?: string;
  severity?: string;
  status?: string;
  author?: string;
}

export interface IncidentTimeline {
  incident: Incident;
  timeline: TimelineEvent[];
  event_count: number;
}

export interface ScenarioRequest {
  sentiment_shift?: number;
  volume_multiplier?: number;
  risk_weight_sentiment?: number;
  risk_weight_anomaly?: number;
  risk_weight_ticket_volume?: number;
  risk_weight_revenue?: number;
  risk_weight_engagement?: number;
}

export interface ScenarioResult {
  baseline_avg_risk: number;
  projected_avg_risk: number;
  delta: number;
  baseline_tier_distribution: Record<string, number>;
  projected_tier_distribution: Record<string, number>;
  signals_analyzed: number;
  high_risk_change: number;
}

export interface RiskWeights {
  sentiment: number;
  anomaly: number;
  ticket_volume: number;
  revenue: number;
  engagement: number;
}

export interface AppSettings {
  risk_weights: RiskWeights;
  retention_days: number;
  use_mock_ml: boolean;
  llm_enabled: boolean;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  // Health
  health: () => apiFetch<{ status: string; version: string; websocket_connections: number; scheduler_active: boolean }>("/api/health"),

  // Dashboard
  dashboardOverview: () => apiFetch<DashboardOverview>("/api/dashboard/overview"),
  dashboardTimeline: (limit = 20) =>
    apiFetch<{ timeline: TimelineEntry[] }>(`/api/dashboard/timeline?limit=${limit}`),

  // Signals
  listSignals: (page = 1, pageSize = 20, source?: string, riskTier?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (source) params.set("source", source);
    if (riskTier) params.set("risk_tier", riskTier);
    return apiFetch<SignalListResponse>(`/api/signals?${params}`);
  },
  getSignal: (id: number) => apiFetch<Signal>(`/api/signals/${id}`),
  explainSignal: (id: number) => apiFetch<SignalExplanation>(`/api/signals/${id}/explain`),
  triggerIngestion: (count = 30) =>
    apiFetch<{ status: string; ingested: number; processed: number }>(
      `/api/signals/ingest?count=${count}`,
      { method: "POST" }
    ),

  // Incidents
  listIncidents: (status?: string, severity?: string, limit = 100) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (severity) params.set("severity", severity);
    params.set("limit", String(limit));
    return apiFetch<Incident[]>(`/api/incidents?${params}`);
  },
  getIncident: (id: number) => apiFetch<Incident>(`/api/incidents/${id}`),
  getIncidentTimeline: (id: number) => apiFetch<IncidentTimeline>(`/api/incidents/${id}/timeline`),
  getIncidentNotes: (id: number) => apiFetch<Note[]>(`/api/incidents/${id}/notes`),
  addIncidentNote: (id: number, content: string, author = "User") =>
    apiFetch<Note>(`/api/incidents/${id}/notes`, {
      method: "POST",
      body: JSON.stringify({ content, author }),
    }),
  acknowledgeIncident: (id: number) =>
    apiFetch<Incident>(`/api/incidents/${id}/acknowledge`, { method: "POST" }),
  resolveIncident: (id: number) =>
    apiFetch<Incident>(`/api/incidents/${id}/resolve`, { method: "POST" }),
  dismissIncident: (id: number) =>
    apiFetch<Incident>(`/api/incidents/${id}/dismiss`, { method: "POST" }),
  reopenIncident: (id: number) =>
    apiFetch<Incident>(`/api/incidents/${id}/reopen`, { method: "POST" }),

  // Risk
  riskOverview: () => apiFetch<RiskOverview>("/api/risk/overview"),
  riskHeatmap: () => apiFetch<HeatmapData>("/api/risk/heatmap"),

  // Correlation
  getCorrelations: (signalId: number, k = 10) =>
    apiFetch<{ signal_id: number; correlations: CorrelationResult[]; total: number }>(
      `/api/correlation/${signalId}?k=${k}`
    ),
  getCorrelationGraph: (signalId: number, depth = 1, k = 8) =>
    apiFetch<CorrelationGraphData>(
      `/api/correlation/graph/${signalId}?depth=${depth}&k=${k}`
    ),

  // Chat
  chat: (query: string) =>
    apiFetch<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),

  // Executive brief
  generateBrief: (
    tone: "executive_concise" | "technical_detailed" | "customer_facing" = "executive_concise",
    lookbackHours = 24
  ) =>
    apiFetch<ExecutiveBrief>(
      `/api/brief/generate?tone=${encodeURIComponent(tone)}&lookback_hours=${lookbackHours}`
    ),

  // Forecast
  forecast: (metricName = "mrr", horizon = 8, lookbackHours = 168) =>
    apiFetch<ForecastResponse>(
      `/api/forecast?metric_name=${encodeURIComponent(metricName)}&horizon=${horizon}&lookback_hours=${lookbackHours}`
    ),
  forecastMetrics: (lookbackHours = 168) =>
    apiFetch<{ metrics: string[]; count: number }>(
      `/api/forecast/metrics?lookback_hours=${lookbackHours}`
    ),

  // Demo
  seedDemoData: () =>
    apiFetch<{ status: string; signals_created?: number; incidents_created?: number; message: string }>(
      "/api/demo/seed",
      { method: "POST" }
    ),
  resetDemoData: () =>
    apiFetch<{ status: string; deleted: number }>("/api/demo/reset", { method: "POST" }),

  // Simulator
  runScenario: (params: ScenarioRequest) =>
    apiFetch<ScenarioResult>("/api/simulator/run", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  // Settings
  getSettings: () => apiFetch<AppSettings>("/api/settings"),
  getRiskWeights: () => apiFetch<RiskWeights>("/api/settings/risk-weights"),
  updateRiskWeights: (weights: RiskWeights) =>
    apiFetch<RiskWeights>("/api/settings/risk-weights", {
      method: "PUT",
      body: JSON.stringify(weights),
    }),
  resetRiskWeights: () =>
    apiFetch<RiskWeights>("/api/settings/risk-weights", { method: "DELETE" }),
};

