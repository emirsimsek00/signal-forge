"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
    AlertTriangle, X, Shield, TrendingUp, Activity,
} from "lucide-react";

interface Toast {
    id: string;
    severity: "critical" | "high" | "moderate" | "info";
    title: string;
    message: string;
    type?: string;
    timestamp: Date;
}

const SEVERITY_CONFIG: Record<string, { bg: string; border: string; icon: typeof AlertTriangle }> = {
    critical: { bg: "rgba(244, 63, 94, 0.95)", border: "#f43f5e", icon: AlertTriangle },
    high: { bg: "rgba(245, 158, 11, 0.95)", border: "#f59e0b", icon: Shield },
    moderate: { bg: "rgba(99, 102, 241, 0.95)", border: "#6366f1", icon: Activity },
    info: { bg: "rgba(34, 211, 238, 0.95)", border: "#22d3ee", icon: TrendingUp },
};

const MAX_VISIBLE = 3;
const AUTO_DISMISS_MS = 8000;

export default function AlertToast() {
    const [toasts, setToasts] = useState<Toast[]>([]);
    const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

    const dismiss = useCallback((id: string) => {
        const timer = timersRef.current.get(id);
        if (timer) clearTimeout(timer);
        timersRef.current.delete(id);
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    const addToast = useCallback(
        (toast: Omit<Toast, "id" | "timestamp">) => {
            const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
            const newToast: Toast = { ...toast, id, timestamp: new Date() };

            setToasts((prev) => {
                const updated = [...prev, newToast];
                // Keep only max visible
                if (updated.length > MAX_VISIBLE) {
                    const removed = updated.slice(0, updated.length - MAX_VISIBLE);
                    removed.forEach((r) => dismiss(r.id));
                    return updated.slice(-MAX_VISIBLE);
                }
                return updated;
            });

            // Auto dismiss
            const timer = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
            timersRef.current.set(id, timer);
        },
        [dismiss]
    );

    // WebSocket listener
    useWebSocket({
        channels: ["alerts"],
        onAlert: (data: Record<string, unknown>) => {
            const payload = data as any;
            if (payload.type === "anomaly") {
                addToast({
                    severity: payload.severity === "critical" ? "critical" : payload.severity === "high" ? "high" : "moderate",
                    title: payload.title || "Anomaly Detected",
                    message: payload.description || "An anomaly was detected in signal patterns",
                    type: "anomaly",
                });
            } else {
                // Signal alert
                const severity = payload.risk_tier === "critical" ? "critical" : "high";
                addToast({
                    severity,
                    title: `${severity.toUpperCase()} Signal`,
                    message: `${payload.source}: ${payload.title || payload.content?.slice(0, 60) || "New alert"}`,
                    type: "signal",
                });
            }
        },
    });

    // Cleanup timers on unmount
    useEffect(() => {
        return () => {
            timersRef.current.forEach((timer) => clearTimeout(timer));
        };
    }, []);

    if (toasts.length === 0) return null;

    return (
        <div
            className="fixed top-4 right-4 z-[9999] flex flex-col gap-2"
            style={{ maxWidth: "380px", width: "100%" }}
        >
            {toasts.map((toast, i) => {
                const config = SEVERITY_CONFIG[toast.severity] || SEVERITY_CONFIG.info;
                const Icon = config.icon;
                return (
                    <div
                        key={toast.id}
                        className="flex items-start gap-3 px-4 py-3 rounded-xl shadow-2xl"
                        style={{
                            background: config.bg,
                            backdropFilter: "blur(20px)",
                            border: `1px solid ${config.border}`,
                            animation: "slideIn 0.3s ease-out",
                            opacity: 1 - i * 0.05,
                        }}
                    >
                        <Icon className="w-5 h-5 text-white flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-white">{toast.title}</p>
                            <p className="text-xs text-white/80 mt-0.5 leading-relaxed truncate">
                                {toast.message}
                            </p>
                        </div>
                        <button
                            onClick={() => dismiss(toast.id)}
                            className="text-white/60 hover:text-white transition-colors flex-shrink-0"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                );
            })}

            <style jsx global>{`
        @keyframes slideIn {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
        </div>
    );
}
