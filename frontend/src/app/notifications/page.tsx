"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ComponentType, FormEvent } from "react";
import {
  api,
  NotificationChannel,
  NotificationLog,
  NotificationPreference,
  NotificationTrigger,
} from "@/lib/api";
import EmptyState from "@/components/EmptyState";
import {
  BellRing,
  CheckCircle2,
  Loader2,
  Mail,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Webhook,
} from "lucide-react";

const TRIGGER_OPTIONS: { id: NotificationTrigger; label: string; description: string }[] = [
  {
    id: "critical_signal",
    label: "Critical Signal",
    description: "Notify when high-severity signals are detected.",
  },
  {
    id: "incident_created",
    label: "Incident Created",
    description: "Notify when a new incident is opened.",
  },
  {
    id: "incident_escalated",
    label: "Incident Escalated",
    description: "Notify when an incident severity increases.",
  },
  {
    id: "incident_resolved",
    label: "Incident Resolved",
    description: "Notify when incidents are resolved.",
  },
  {
    id: "daily_digest",
    label: "Daily Digest",
    description: "Receive a daily summary of key risk activity.",
  },
];

const CHANNEL_OPTIONS: {
  id: NotificationChannel;
  label: string;
  placeholder: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
}[] = [
  {
    id: "email",
    label: "Email",
    placeholder: "alerts@yourcompany.com",
    description: "Send formatted alert and incident emails.",
    icon: Mail,
  },
  {
    id: "slack",
    label: "Slack Webhook",
    placeholder: "https://hooks.slack.com/services/...",
    description: "Post alert cards to a Slack channel.",
    icon: Webhook,
  },
];

const DEFAULT_TRIGGERS: NotificationTrigger[] = ["critical_signal", "incident_created"];

function parseTriggers(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export default function NotificationsPage() {
  const [preferences, setPreferences] = useState<NotificationPreference[]>([]);
  const [logs, setLogs] = useState<NotificationLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshingLogs, setRefreshingLogs] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [channel, setChannel] = useState<NotificationChannel>("email");
  const [target, setTarget] = useState("");
  const [triggers, setTriggers] = useState<NotificationTrigger[]>(DEFAULT_TRIGGERS);

  const selectedChannel = useMemo(
    () => CHANNEL_OPTIONS.find((option) => option.id === channel) || CHANNEL_OPTIONS[0],
    [channel]
  );

  const setSuccessMessage = useCallback((message: string) => {
    setSuccess(message);
    setTimeout(() => setSuccess(null), 2500);
  }, []);

  const loadAll = useCallback(async (initial = false) => {
    if (initial) setLoading(true);
    setError(null);
    try {
      const [prefs, logData] = await Promise.all([api.getPreferences(), api.getLogs(50)]);
      setPreferences(prefs.preferences);
      setLogs(logData.logs);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load notifications");
    } finally {
      if (initial) setLoading(false);
    }
  }, []);

  const loadLogs = useCallback(async () => {
    setRefreshingLogs(true);
    try {
      const logData = await api.getLogs(50);
      setLogs(logData.logs);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh notification logs");
    } finally {
      setRefreshingLogs(false);
    }
  }, []);

  useEffect(() => {
    void loadAll(true);
  }, [loadAll]);

  const toggleTrigger = (value: NotificationTrigger) => {
    setTriggers((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value]
    );
  };

  const createPreference = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    const normalizedTarget = target.trim();
    if (!normalizedTarget) {
      setError("Target is required.");
      return;
    }
    if (triggers.length === 0) {
      setError("Select at least one trigger.");
      return;
    }

    setSaving(true);
    try {
      await api.createPreference({
        channel,
        target: normalizedTarget,
        triggers,
      });
      setTarget("");
      setTriggers(DEFAULT_TRIGGERS);
      await loadAll(false);
      setSuccessMessage("Notification channel added.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create notification preference");
    } finally {
      setSaving(false);
    }
  };

  const deletePreference = async (prefId: number) => {
    setDeletingId(prefId);
    setError(null);
    try {
      await api.deletePreference(prefId);
      await loadAll(false);
      setSuccessMessage("Notification channel removed.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete preference");
    } finally {
      setDeletingId(null);
    }
  };

  const sendTest = async (pref: NotificationPreference) => {
    setTestingId(pref.id);
    setError(null);
    try {
      await api.testNotification(pref.channel, pref.target);
      await loadLogs();
      setSuccessMessage("Test notification sent.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send test notification");
    } finally {
      setTestingId(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-64 skeleton" />
        <div className="h-56 skeleton" />
        <div className="h-44 skeleton" />
        <div className="h-64 skeleton" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Notifications</h1>
        <p className="text-sm text-slate-500 mt-1">
          Manage delivery channels and review recent notification activity.
        </p>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-xl border text-sm text-rose-300 bg-rose-500/10 border-rose-500/30">
          {error}
        </div>
      )}
      {success && (
        <div className="px-4 py-3 rounded-xl border text-sm text-emerald-300 bg-emerald-500/10 border-emerald-500/30 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          {success}
        </div>
      )}

      <div className="glass-card p-6">
        <div className="flex items-center gap-2 mb-5">
          <Plus className="w-4 h-4 text-indigo-400" />
          <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Add Channel</h2>
        </div>

        <form className="space-y-4" onSubmit={createPreference}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <label className="space-y-1.5">
              <span className="text-xs text-slate-400 uppercase tracking-wider">Channel</span>
              <select
                value={channel}
                onChange={(event) => setChannel(event.target.value as NotificationChannel)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/50 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-indigo-400/70"
              >
                {CHANNEL_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-xs text-slate-400 uppercase tracking-wider">Target</span>
              <input
                value={target}
                onChange={(event) => setTarget(event.target.value)}
                placeholder={selectedChannel.placeholder}
                className="w-full rounded-xl border border-slate-700 bg-slate-950/50 px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-indigo-400/70"
              />
            </label>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-4">
            <div className="flex items-center gap-2 mb-3">
              <selectedChannel.icon className="w-4 h-4 text-indigo-300" />
              <p className="text-sm font-medium text-white">{selectedChannel.label}</p>
              <p className="text-xs text-slate-500">{selectedChannel.description}</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {TRIGGER_OPTIONS.map((trigger) => {
                const checked = triggers.includes(trigger.id);
                return (
                  <label
                    key={trigger.id}
                    className="flex items-start gap-2.5 rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2.5"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleTrigger(trigger.id)}
                      className="mt-0.5 accent-indigo-500"
                    />
                    <span>
                      <span className="text-sm text-slate-200 block">{trigger.label}</span>
                      <span className="text-xs text-slate-500">{trigger.description}</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          <button
            type="submit"
            disabled={saving}
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Add Notification Channel
          </button>
        </form>
      </div>

      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BellRing className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Configured Channels</h2>
          </div>
          <span className="text-xs text-slate-500">{preferences.length} active</span>
        </div>

        {preferences.length === 0 ? (
          <EmptyState
            title="No channels configured"
            description="Add an email or Slack webhook target to receive alert notifications."
          />
        ) : (
          <div className="space-y-3">
            {preferences.map((pref) => {
              const triggerList = parseTriggers(pref.triggers);
              return (
                <div
                  key={pref.id}
                  className="rounded-xl border border-slate-800 bg-slate-950/30 px-4 py-3.5 flex items-start justify-between gap-4"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span
                        className="text-[0.65rem] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border"
                        style={{
                          background:
                            pref.channel === "email"
                              ? "rgba(34,211,238,0.12)"
                              : "rgba(99,102,241,0.12)",
                          borderColor:
                            pref.channel === "email"
                              ? "rgba(34,211,238,0.35)"
                              : "rgba(99,102,241,0.35)",
                          color: pref.channel === "email" ? "#22d3ee" : "#818cf8",
                        }}
                      >
                        {pref.channel}
                      </span>
                      <span className="text-xs text-slate-500">
                        Added {new Date(pref.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-sm text-slate-200 break-all">{pref.target}</p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {triggerList.map((trigger) => (
                        <span
                          key={`${pref.id}-${trigger}`}
                          className="text-[0.65rem] px-2 py-0.5 rounded-md text-slate-300 bg-white/5 border border-white/10"
                        >
                          {trigger.replaceAll("_", " ")}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => sendTest(pref)}
                      disabled={testingId === pref.id}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs text-slate-300 hover:border-indigo-400/50 disabled:opacity-60"
                    >
                      {testingId === pref.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Send className="w-3.5 h-3.5" />
                      )}
                      Test
                    </button>
                    <button
                      onClick={() => deletePreference(pref.id)}
                      disabled={deletingId === pref.id}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/20 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300 hover:border-rose-400/40 disabled:opacity-60"
                    >
                      {deletingId === pref.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                      Delete
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BellRing className="w-4 h-4 text-indigo-400" />
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Delivery Log</h2>
          </div>
          <button
            onClick={loadLogs}
            disabled={refreshingLogs}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs text-slate-300 hover:border-indigo-400/50 disabled:opacity-60"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshingLogs ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {logs.length === 0 ? (
          <EmptyState
            title="No notification events yet"
            description="Run a test notification or wait for a trigger event to populate this log."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Channel</th>
                  <th>Trigger</th>
                  <th>Status</th>
                  <th>Subject</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td className="capitalize">{log.channel}</td>
                    <td>{log.trigger.replaceAll("_", " ")}</td>
                    <td>
                      <span
                        className="text-[0.65rem] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border"
                        style={{
                          background:
                            log.status === "sent"
                              ? "rgba(16,185,129,0.12)"
                              : "rgba(244,63,94,0.12)",
                          borderColor:
                            log.status === "sent"
                              ? "rgba(16,185,129,0.3)"
                              : "rgba(244,63,94,0.3)",
                          color: log.status === "sent" ? "#34d399" : "#fb7185",
                        }}
                      >
                        {log.status}
                      </span>
                    </td>
                    <td className="max-w-64 truncate text-slate-300">{log.subject}</td>
                    <td className="max-w-72 truncate text-rose-300/80">{log.error || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
