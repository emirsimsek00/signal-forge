import { Inbox, AlertCircle, RefreshCw } from "lucide-react";

interface EmptyStateProps {
    icon?: "empty" | "error";
    title: string;
    description?: string;
    action?: { label: string; onClick: () => void };
}

/**
 * Consistent empty/error state component used across all pages.
 */
export default function EmptyState({ icon = "empty", title, description, action }: EmptyStateProps) {
    const Icon = icon === "error" ? AlertCircle : Inbox;
    return (
        <div className="empty-state fade-in">
            <div className="empty-state-icon">
                <Icon className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
            {description && <p className="text-xs text-slate-500 mb-4 max-w-sm mx-auto">{description}</p>}
            {action && (
                <button onClick={action.onClick} className="btn-primary inline-flex items-center gap-2 text-xs">
                    <RefreshCw className="w-3.5 h-3.5" /> {action.label}
                </button>
            )}
        </div>
    );
}
