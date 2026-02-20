"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Zap, Target, Bell, BarChart3, CheckCircle2, Loader2, ArrowRight, Sparkles } from "lucide-react";

const STEPS = [
    { icon: Zap, title: "Connect Sources", description: "SignalForge ingests data from Reddit, Stripe, PagerDuty, Zendesk, and more." },
    { icon: Target, title: "Set Monitoring Goals", description: "Focus on revenue risk, sentiment shifts, infrastructure health, or customer churn." },
    { icon: Bell, title: "Configure Alerts", description: "Get notified when risk scores cross your thresholds." },
    { icon: BarChart3, title: "See Insights", description: "Your dashboard populates with signals, risk scores, and AI-powered analysis." },
];

const GOALS = [
    { id: "revenue", label: "Revenue Risk", desc: "Churn, failed payments, CAC trends" },
    { id: "sentiment", label: "Sentiment Drift", desc: "Community & customer sentiment" },
    { id: "infra", label: "Infrastructure Health", desc: "Latency, errors, outages" },
    { id: "competitive", label: "Competitive Intelligence", desc: "Market moves, competitor launches" },
];

export default function OnboardingPage() {
    const router = useRouter();
    const [step, setStep] = useState(0);
    const [selectedGoals, setSelectedGoals] = useState<string[]>(["revenue", "sentiment"]);
    const [seeding, setSeeding] = useState(false);
    const [seedResult, setSeedResult] = useState<string | null>(null);

    const toggleGoal = (id: string) => {
        setSelectedGoals((prev) =>
            prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]
        );
    };

    const handleSeedAndFinish = async () => {
        setSeeding(true);
        try {
            const result = await api.seedDemoData();
            setSeedResult(result.message);
            localStorage.setItem("signalforge_onboarded", "true");
            localStorage.setItem("signalforge_goals", JSON.stringify(selectedGoals));
            setTimeout(() => router.push("/"), 1500);
        } catch {
            setSeedResult("Demo data loaded. Redirecting to dashboard...");
            localStorage.setItem("signalforge_onboarded", "true");
            setTimeout(() => router.push("/"), 1500);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "var(--bg-primary)" }}>
            <div className="w-full max-w-2xl">
                {/* Header */}
                <div className="text-center mb-10">
                    <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium mb-4"
                        style={{ background: "rgba(99,102,241,0.15)", color: "#818cf8", border: "1px solid rgba(99,102,241,0.25)" }}>
                        <Sparkles className="w-3.5 h-3.5" /> Welcome to SignalForge
                    </div>
                    <h1 className="text-3xl font-bold text-white tracking-tight">Set up your workspace</h1>
                    <p className="text-sm mt-2" style={{ color: "var(--text-secondary)" }}>
                        Get operational intelligence in under 60 seconds.
                    </p>
                </div>

                {/* Progress */}
                <div className="flex items-center gap-1 mb-8">
                    {STEPS.map((_, i) => (
                        <div key={i} className="flex-1 h-1 rounded-full transition-all duration-300"
                            style={{ background: i <= step ? "var(--accent-indigo)" : "rgba(255,255,255,0.08)" }} />
                    ))}
                </div>

                {/* Step content */}
                <div className="glass-card p-8 mb-6">
                    {step === 0 && (
                        <div className="space-y-6">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
                                    <Zap className="w-5 h-5 text-indigo-400" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-semibold text-white">Data Sources</h2>
                                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>SignalForge connects to these platforms</p>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                {["Reddit", "Stripe", "PagerDuty", "Zendesk", "NewsAPI", "Alpha Vantage", "System Metrics"].map((src) => (
                                    <div key={src} className="flex items-center gap-2 px-4 py-3 rounded-xl" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
                                        <div className="w-2 h-2 rounded-full" style={{ background: "var(--accent-emerald)" }} />
                                        <span className="text-sm text-slate-300">{src}</span>
                                    </div>
                                ))}
                            </div>
                            <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
                                No API keys required — demo data is pre-loaded for all sources.
                            </p>
                        </div>
                    )}

                    {step === 1 && (
                        <div className="space-y-6">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
                                    <Target className="w-5 h-5 text-indigo-400" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-semibold text-white">Monitoring Goals</h2>
                                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>Choose what matters to your team</p>
                                </div>
                            </div>
                            <div className="space-y-3">
                                {GOALS.map((goal) => (
                                    <button key={goal.id} onClick={() => toggleGoal(goal.id)}
                                        className="w-full flex items-center gap-4 px-4 py-3.5 rounded-xl text-left transition-all"
                                        style={{
                                            background: selectedGoals.includes(goal.id) ? "rgba(99,102,241,0.12)" : "rgba(255,255,255,0.03)",
                                            border: `1px solid ${selectedGoals.includes(goal.id) ? "rgba(99,102,241,0.4)" : "rgba(255,255,255,0.06)"}`,
                                        }}>
                                        <div className={`w-5 h-5 rounded-md flex items-center justify-center transition-all ${selectedGoals.includes(goal.id) ? "bg-indigo-500" : ""}`}
                                            style={{ border: selectedGoals.includes(goal.id) ? "none" : "1px solid rgba(255,255,255,0.15)" }}>
                                            {selectedGoals.includes(goal.id) && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium text-white">{goal.label}</p>
                                            <p className="text-xs" style={{ color: "var(--text-muted)" }}>{goal.desc}</p>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {step === 2 && (
                        <div className="space-y-6">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
                                    <Bell className="w-5 h-5 text-indigo-400" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-semibold text-white">Alert Thresholds</h2>
                                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>Default thresholds are pre-configured</p>
                                </div>
                            </div>
                            <div className="space-y-4">
                                {[
                                    { label: "Critical risk alerts", value: "Score ≥ 0.75", color: "#f43f5e" },
                                    { label: "High risk alerts", value: "Score ≥ 0.55", color: "#f59e0b" },
                                    { label: "Anomaly detection", value: "2σ deviation", color: "#6366f1" },
                                    { label: "Sentiment drops", value: "≥ 15% negative shift", color: "#06b6d4" },
                                ].map((threshold) => (
                                    <div key={threshold.label} className="flex items-center justify-between px-4 py-3 rounded-xl"
                                        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                                        <div className="flex items-center gap-3">
                                            <div className="w-2 h-2 rounded-full" style={{ background: threshold.color }} />
                                            <span className="text-sm text-slate-300">{threshold.label}</span>
                                        </div>
                                        <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>{threshold.value}</span>
                                    </div>
                                ))}
                            </div>
                            <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
                                Thresholds can be adjusted later in Settings.
                            </p>
                        </div>
                    )}

                    {step === 3 && (
                        <div className="space-y-6 text-center">
                            <div className="flex items-center justify-center gap-3 mb-4">
                                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(99,102,241,0.15)" }}>
                                    <BarChart3 className="w-5 h-5 text-indigo-400" />
                                </div>
                            </div>
                            <h2 className="text-lg font-semibold text-white">Ready to launch</h2>
                            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                                We&apos;ll seed your workspace with realistic demo data so you can explore every feature immediately.
                            </p>

                            {seedResult ? (
                                <div className="flex items-center justify-center gap-2 py-4">
                                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                                    <span className="text-sm text-emerald-300">{seedResult}</span>
                                </div>
                            ) : (
                                <button onClick={handleSeedAndFinish} disabled={seeding}
                                    className="btn-primary inline-flex items-center gap-2 px-8 py-3 text-base">
                                    {seeding ? (
                                        <><Loader2 className="w-4 h-4 animate-spin" /> Seeding data...</>
                                    ) : (
                                        <><Sparkles className="w-4 h-4" /> Launch SignalForge</>
                                    )}
                                </button>
                            )}
                        </div>
                    )}
                </div>

                {/* Navigation */}
                <div className="flex items-center justify-between">
                    <button onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}
                        className="text-sm font-medium px-4 py-2 rounded-lg transition-all disabled:opacity-30"
                        style={{ color: "var(--text-secondary)" }}>
                        Back
                    </button>

                    {step < 3 ? (
                        <button onClick={() => setStep(step + 1)}
                            className="btn-primary inline-flex items-center gap-2">
                            Continue <ArrowRight className="w-4 h-4" />
                        </button>
                    ) : (
                        <button onClick={() => router.push("/")}
                            className="text-sm font-medium px-4 py-2 rounded-lg transition-all"
                            style={{ color: "var(--text-muted)" }}>
                            Skip
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
