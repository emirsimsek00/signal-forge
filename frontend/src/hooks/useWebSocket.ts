"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface WebSocketMessage {
    type: "signal" | "alert" | "heartbeat" | "ack" | "pong" | "subscribed";
    data?: Record<string, unknown>;
    channels?: string[];
    message?: string;
}

interface UseWebSocketOptions {
    channels?: string[];
    onSignal?: (data: Record<string, unknown>) => void;
    onAlert?: (data: Record<string, unknown>) => void;
    enabled?: boolean;
}

interface UseWebSocketReturn {
    connected: boolean;
    lastSignal: Record<string, unknown> | null;
    lastAlert: Record<string, unknown> | null;
    signalCount: number;
    alertCount: number;
    send: (data: Record<string, unknown>) => void;
}

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
    const {
        channels = ["all"],
        onSignal,
        onAlert,
        enabled = true,
    } = options;

    const [connected, setConnected] = useState(false);
    const [lastSignal, setLastSignal] = useState<Record<string, unknown> | null>(null);
    const [lastAlert, setLastAlert] = useState<Record<string, unknown> | null>(null);
    const [signalCount, setSignalCount] = useState(0);
    const [alertCount, setAlertCount] = useState(0);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const reconnectDelayRef = useRef(1000);

    const connect = useCallback(function connectSocket() {
        if (!enabled) return;

        const channelsParam = channels.join(",");
        const url = `${WS_BASE}/ws/signals?channels=${channelsParam}`;

        try {
            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                setConnected(true);
                reconnectDelayRef.current = 1000; // reset backoff
            };

            ws.onmessage = (event) => {
                try {
                    const msg: WebSocketMessage = JSON.parse(event.data);

                    switch (msg.type) {
                        case "signal":
                            if (msg.data) {
                                setLastSignal(msg.data);
                                setSignalCount((c) => c + 1);
                                onSignal?.(msg.data);
                            }
                            break;
                        case "alert":
                            if (msg.data) {
                                setLastAlert(msg.data);
                                setAlertCount((c) => c + 1);
                                onAlert?.(msg.data);
                            }
                            break;
                        case "heartbeat":
                            // respond to keep alive
                            ws.send(JSON.stringify({ type: "ping" }));
                            break;
                    }
                } catch {
                    // ignore parse errors
                }
            };

            ws.onclose = () => {
                setConnected(false);
                wsRef.current = null;
                // Exponential backoff reconnect
                if (enabled) {
                    reconnectTimeoutRef.current = setTimeout(() => {
                        reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
                        connectSocket();
                    }, reconnectDelayRef.current);
                }
            };

            ws.onerror = () => {
                ws.close();
            };
        } catch {
            // connection failed, will retry via onclose
        }
    }, [enabled, channels, onSignal, onAlert]);

    useEffect(() => {
        connect();
        return () => {
            if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
            if (wsRef.current) wsRef.current.close();
        };
    }, [connect]);

    const send = useCallback((data: Record<string, unknown>) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(data));
        }
    }, []);

    return { connected, lastSignal, lastAlert, signalCount, alertCount, send };
}
