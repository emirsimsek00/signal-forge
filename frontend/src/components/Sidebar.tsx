"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    Radio,
    AlertTriangle,
    Shield,
    Bell,
    FileText,
    GitBranch,
    MessageSquare,
    Activity,
    Zap,
    FlaskConical,
    Settings2,
    HeartPulse,
    Rocket,
} from "lucide-react";

const NAV_SECTIONS = [
    {
        label: null as string | null,
        items: [
            { href: "/", label: "Overview", icon: LayoutDashboard },
            { href: "/signals", label: "Signals", icon: Radio },
            { href: "/chat", label: "AI Chat", icon: MessageSquare },
        ],
    },
    {
        label: "Intelligence",
        items: [
            { href: "/correlation", label: "Correlations", icon: GitBranch },
            { href: "/anomalies", label: "Anomalies", icon: Activity },
            { href: "/incidents", label: "Incidents", icon: AlertTriangle },
            { href: "/risk", label: "Risk Map", icon: Shield },
        ],
    },
    {
        label: "Operations",
        items: [
            { href: "/alerts", label: "Alerts", icon: Bell },
            { href: "/brief", label: "Exec Brief", icon: FileText },
            { href: "/simulator", label: "Simulator", icon: FlaskConical },
        ],
    },
    {
        label: "System",
        items: [
            { href: "/settings", label: "Settings", icon: Settings2 },
            { href: "/health", label: "Health", icon: HeartPulse },
            { href: "/onboarding", label: "Setup", icon: Rocket },
        ],
    },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="sidebar fixed left-0 top-0 bottom-0 w-64 flex flex-col z-50">
            {/* Logo */}
            <div className="p-6 pb-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                        style={{ background: "var(--gradient-primary)" }}>
                        <Zap className="w-5 h-5 text-white" />
                    </div>
                    <div>
                        <h1 className="text-lg font-bold text-white tracking-tight">SignalForge</h1>
                        <p className="text-[0.65rem] text-slate-500 tracking-widest uppercase">AI Ops Platform</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-4 space-y-4 overflow-y-auto">
                {NAV_SECTIONS.map((section, si) => (
                    <div key={si}>
                        {section.label && (
                            <p className="text-[0.6rem] text-slate-600 uppercase tracking-[0.12em] font-semibold px-3 mb-1">
                                {section.label}
                            </p>
                        )}
                        <div className="space-y-0.5">
                            {section.items.map((item) => {
                                const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                                const Icon = item.icon;
                                return (
                                    <Link key={item.href} href={item.href}
                                        className={`sidebar-link ${isActive ? "active" : ""}`}>
                                        <Icon className="w-[18px] h-[18px]" />
                                        <span>{item.label}</span>
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </nav>

            {/* Status footer */}
            <div className="p-4 mx-4 mb-4 rounded-xl" style={{ background: "rgba(99, 102, 241, 0.08)", border: "1px solid rgba(99, 102, 241, 0.12)" }}>
                <div className="flex items-center gap-2 mb-1">
                    <div className="pulse-dot" style={{ background: "var(--accent-emerald)" }} />
                    <span className="text-xs font-medium text-emerald-400">System Online</span>
                </div>
                <p className="text-[0.65rem] text-slate-500">v0.5.0 · AI Ops Platform</p>
            </div>
        </aside>
    );
}
