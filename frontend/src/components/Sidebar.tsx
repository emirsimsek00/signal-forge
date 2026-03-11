"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import {
    LayoutDashboard,
    Radio,
    AlertTriangle,
    Shield,
    Bell,
    BellRing,
    FileText,
    GitBranch,
    MessageSquare,
    Activity,
    Zap,
    FlaskConical,
    Settings2,
    HeartPulse,
    Rocket,
    LogOut,
    UserRound,
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
            { href: "/notifications", label: "Notifications", icon: BellRing },
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
    const router = useRouter();
    const { user, tenant, isDemo, signOut } = useAuth();
    const [signingOut, setSigningOut] = useState(false);

    const userName = isDemo
        ? "Demo User"
        : ((user?.user_metadata?.display_name as string | undefined) ||
            (user?.email ? user.email.split("@")[0] : "Guest"));
    const workspaceName = tenant?.name || (isDemo ? "Demo Workspace" : "No Workspace");

    const handleSignOut = async () => {
        setSigningOut(true);
        try {
            await signOut();
            router.replace(isDemo ? "/" : "/login");
        } finally {
            setSigningOut(false);
        }
    };

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

            {/* Auth summary */}
            <div className="mx-4 mb-3 rounded-xl p-3" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <div className="flex items-start gap-2">
                    <div className="mt-0.5 w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(99, 102, 241, 0.14)" }}>
                        <UserRound className="w-4 h-4 text-indigo-300" />
                    </div>
                    <div className="min-w-0">
                        <p className="text-xs text-white font-medium truncate">{userName}</p>
                        <p className="text-[0.65rem] text-slate-500 truncate">{workspaceName}</p>
                    </div>
                </div>
                {isDemo ? (
                    <p className="mt-3 text-[0.65rem] text-slate-500">
                        Demo mode active (authentication disabled).
                    </p>
                ) : (
                    <button
                        onClick={handleSignOut}
                        disabled={signingOut}
                        className="mt-3 w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs text-slate-300 hover:border-indigo-400/50 transition disabled:opacity-60"
                    >
                        <LogOut className="w-3.5 h-3.5" />
                        {signingOut ? "Signing out..." : "Sign Out"}
                    </button>
                )}
            </div>

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
