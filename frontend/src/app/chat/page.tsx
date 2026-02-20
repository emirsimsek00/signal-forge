"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { api, ChatResponse, ChatCitedSignal } from "@/lib/api";
import {
    MessageSquare, Send, Loader2, AlertTriangle, Search, BarChart3,
    Hash, Sparkles, ExternalLink,
} from "lucide-react";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    intent?: string;
    cited_signals?: ChatCitedSignal[];
    signal_count?: number;
    timestamp: Date;
}

const QUICK_ASKS = [
    "Summarize the top risks",
    "Show critical signals",
    "How many signals from Reddit?",
    "Find signals about outages",
    "What are the negative sentiment signals?",
    "Show news signals from today",
];

const INTENT_ICONS: Record<string, typeof Search> = {
    search: Search,
    summarize: BarChart3,
    count: Hash,
    analyze: Sparkles,
    compare: Sparkles,
};

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    const sendMessage = async (query: string) => {
        if (!query.trim() || loading) return;

        const userMsg: Message = {
            id: `u-${Date.now()}`,
            role: "user",
            content: query.trim(),
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            const response: ChatResponse = await api.chat(query.trim());

            const assistantMsg: Message = {
                id: `a-${Date.now()}`,
                role: "assistant",
                content: response.answer,
                intent: response.intent,
                cited_signals: response.cited_signals,
                signal_count: response.signal_count,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
        } catch (e) {
            const errMsg: Message = {
                id: `e-${Date.now()}`,
                role: "assistant",
                content: "Sorry, I encountered an error processing your query. Make sure the backend is running.",
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errMsg]);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        sendMessage(input);
    };

    const renderMarkdown = (text: string) => {
        // Simple markdown rendering for bold, lists, headings, code
        const lines = text.split("\n");
        return lines.map((line, i) => {
            // Headings
            if (line.startsWith("###")) {
                return (
                    <h4 key={i} className="text-sm font-semibold text-white mt-3 mb-1">
                        {line.replace(/^###\s*/, "")}
                    </h4>
                );
            }
            if (line.startsWith("##")) {
                return (
                    <h3 key={i} className="text-base font-semibold text-white mt-3 mb-1">
                        {line.replace(/^##\s*/, "")}
                    </h3>
                );
            }

            // List items
            if (line.startsWith("- ")) {
                const content = line.replace(/^-\s*/, "");
                return (
                    <div key={i} className="flex gap-2 pl-2 py-0.5">
                        <span className="text-slate-600 mt-0.5">•</span>
                        <span className="text-sm text-slate-300" dangerouslySetInnerHTML={{
                            __html: formatInline(content)
                        }} />
                    </div>
                );
            }

            // Empty line
            if (!line.trim()) return <div key={i} className="h-2" />;

            // Regular text
            return (
                <p key={i} className="text-sm text-slate-300" dangerouslySetInnerHTML={{
                    __html: formatInline(line)
                }} />
            );
        });
    };

    const formatInline = (text: string) => {
        return text
            .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
            .replace(/`(.+?)`/g, '<code class="px-1.5 py-0.5 rounded text-xs font-mono" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc;">$1</code>')
            .replace(/#(\d+)/g, '<span class="text-indigo-400 font-medium">#$1</span>');
    };

    return (
        <div className="flex flex-col h-[calc(100vh-2rem)]">
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
                <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center"
                    style={{ background: "var(--gradient-primary)" }}
                >
                    <MessageSquare className="w-5 h-5 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight">AI Chat</h1>
                    <p className="text-sm text-slate-500">
                        Ask questions about your signals in natural language
                    </p>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto space-y-4 pr-2 mb-4">
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <div
                            className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
                            style={{ background: "rgba(99, 102, 241, 0.1)", border: "1px solid rgba(99, 102, 241, 0.15)" }}
                        >
                            <Sparkles className="w-8 h-8 text-indigo-400" />
                        </div>
                        <h2 className="text-lg font-semibold text-white mb-1">Signal Intelligence Assistant</h2>
                        <p className="text-sm text-slate-500 mb-6 max-w-md">
                            Ask me anything about your signals. I can search, summarize, analyze, and count signals using natural language.
                        </p>
                        <div className="grid grid-cols-2 gap-2 max-w-lg">
                            {QUICK_ASKS.map((q) => (
                                <button
                                    key={q}
                                    onClick={() => sendMessage(q)}
                                    className="text-left text-sm px-4 py-3 rounded-xl transition-all"
                                    style={{
                                        background: "rgba(255, 255, 255, 0.03)",
                                        border: "1px solid rgba(255, 255, 255, 0.06)",
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.background = "rgba(99, 102, 241, 0.08)";
                                        e.currentTarget.style.borderColor = "rgba(99, 102, 241, 0.2)";
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.background = "rgba(255, 255, 255, 0.03)";
                                        e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.06)";
                                    }}
                                >
                                    <span className="text-slate-400">{q}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                ) : (
                    messages.map((msg) => (
                        <div
                            key={msg.id}
                            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                        >
                            <div
                                className={`max-w-[80%] rounded-2xl px-5 py-3 ${msg.role === "user" ? "" : ""
                                    }`}
                                style={{
                                    background:
                                        msg.role === "user"
                                            ? "var(--gradient-primary)"
                                            : "rgba(255, 255, 255, 0.04)",
                                    border:
                                        msg.role === "user"
                                            ? "none"
                                            : "1px solid rgba(255, 255, 255, 0.06)",
                                }}
                            >
                                {/* Intent badge */}
                                {msg.intent && msg.role === "assistant" && (
                                    <div className="flex items-center gap-2 mb-2">
                                        {(() => {
                                            const Icon = INTENT_ICONS[msg.intent] || Search;
                                            return <Icon size={12} className="text-indigo-400" />;
                                        })()}
                                        <span className="text-[0.65rem] uppercase tracking-wider text-indigo-400 font-medium">
                                            {msg.intent}
                                        </span>
                                        {msg.signal_count !== undefined && (
                                            <span className="text-[0.65rem] text-slate-600">
                                                · {msg.signal_count} signals matched
                                            </span>
                                        )}
                                    </div>
                                )}

                                {/* Message content */}
                                {msg.role === "user" ? (
                                    <p className="text-sm text-white">{msg.content}</p>
                                ) : (
                                    <div>{renderMarkdown(msg.content)}</div>
                                )}

                                {/* Cited signals */}
                                {msg.cited_signals && msg.cited_signals.length > 0 && (
                                    <div className="mt-3 pt-3" style={{ borderTop: "1px solid rgba(255, 255, 255, 0.06)" }}>
                                        <p className="text-[0.65rem] uppercase tracking-wider text-slate-600 mb-2 font-medium">
                                            Referenced Signals
                                        </p>
                                        <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
                                            {msg.cited_signals.slice(0, 6).map((sig) => (
                                                <div
                                                    key={sig.id}
                                                    className="flex items-center gap-2 px-3 py-2 rounded-lg transition-colors cursor-pointer"
                                                    style={{ background: "rgba(255, 255, 255, 0.02)" }}
                                                    title={sig.snippet}
                                                >
                                                    <span className={`source-badge source-${sig.source}`} style={{ fontSize: "0.6rem", padding: "1px 6px" }}>
                                                        {sig.source}
                                                    </span>
                                                    <span className="text-xs text-slate-400 truncate flex-1">
                                                        {sig.title || sig.snippet.slice(0, 50)}
                                                    </span>
                                                    {sig.risk_tier && (
                                                        <span className={`badge badge-${sig.risk_tier}`} style={{ fontSize: "0.6rem" }}>
                                                            {sig.risk_tier}
                                                        </span>
                                                    )}
                                                    <ExternalLink size={10} className="text-slate-600" />
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Timestamp */}
                                <p className="text-[0.6rem] text-slate-600 mt-2">
                                    {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                </p>
                            </div>
                        </div>
                    ))
                )}

                {/* Typing indicator */}
                {loading && (
                    <div className="flex justify-start">
                        <div
                            className="rounded-2xl px-5 py-4"
                            style={{ background: "rgba(255, 255, 255, 0.04)", border: "1px solid rgba(255, 255, 255, 0.06)" }}
                        >
                            <div className="flex items-center gap-2">
                                <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                                <span className="text-sm text-slate-500">Analyzing signals...</span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <form
                onSubmit={handleSubmit}
                className="flex items-center gap-3 p-3 rounded-2xl"
                style={{
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
            >
                <MessageSquare className="w-5 h-5 text-slate-600 flex-shrink-0" />
                <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask about your signals..."
                    className="flex-1 bg-transparent text-sm text-white placeholder-slate-600 focus:outline-none"
                    disabled={loading}
                />
                <button
                    type="submit"
                    disabled={!input.trim() || loading}
                    className="w-9 h-9 rounded-xl flex items-center justify-center transition-all"
                    style={{
                        background: input.trim() ? "var(--gradient-primary)" : "rgba(255, 255, 255, 0.05)",
                        opacity: input.trim() ? 1 : 0.4,
                    }}
                >
                    <Send className="w-4 h-4 text-white" />
                </button>
            </form>
        </div>
    );
}
