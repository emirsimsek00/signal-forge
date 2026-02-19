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
    Zap,
} from "lucide-react";

const NAV_ITEMS = [
    { href: "/", label: "Overview", icon: LayoutDashboard },
    { href: "/signals", label: "Signals", icon: Radio },
    { href: "/incidents", label: "Incidents", icon: AlertTriangle },
    { href: "/risk", label: "Risk Map", icon: Shield },
    { href: "/alerts", label: "Alerts", icon: Bell },
    { href: "/brief", label: "Exec Brief", icon: FileText },
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
                        <p className="text-[0.65rem] text-slate-500 tracking-widest uppercase">AI Ops Copilot</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-4 space-y-1">
                {NAV_ITEMS.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`sidebar-link ${isActive ? "active" : ""}`}
                        >
                            <Icon className="w-[18px] h-[18px]" />
                            <span>{item.label}</span>
                        </Link>
                    );
                })}
            </nav>

            {/* Status footer */}
            <div className="p-4 mx-4 mb-4 rounded-xl" style={{ background: "rgba(99, 102, 241, 0.08)", border: "1px solid rgba(99, 102, 241, 0.12)" }}>
                <div className="flex items-center gap-2 mb-1">
                    <div className="pulse-dot" style={{ background: "var(--accent-emerald)" }} />
                    <span className="text-xs font-medium text-emerald-400">System Online</span>
                </div>
                <p className="text-[0.65rem] text-slate-500">Mock ML · Demo Mode</p>
            </div>
        </aside>
    );
}
