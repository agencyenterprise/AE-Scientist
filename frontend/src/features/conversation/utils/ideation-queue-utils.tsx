import type { ReactNode } from "react";
import { CheckCircle2, Clock, Loader2, AlertCircle, FileQuestion } from "lucide-react";
import type { Conversation } from "@/shared/lib/api-adapters";
import type {
  IdeaStatus,
  StatusFilterOption,
  IdeaStatusConfig,
  StatusFilterConfig,
} from "../types/ideation-queue.types";

// ===== Status Badge Configuration (OCP: extend by adding entries) =====

export const IDEA_STATUS_CONFIG: Record<IdeaStatus, IdeaStatusConfig> = {
  no_idea: {
    label: "No idea",
    className: "bg-slate-500/15 text-slate-400",
    icon: FileQuestion,
  },
  pending_launch: {
    label: "Pending",
    className: "bg-amber-500/15 text-amber-400",
    icon: Clock,
  },
  in_research: {
    label: "Running",
    className: "bg-sky-500/15 text-sky-400",
    icon: Loader2,
  },
  completed: {
    label: "Completed",
    className: "bg-emerald-500/15 text-emerald-400",
    icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    className: "bg-red-500/15 text-red-400",
    icon: AlertCircle,
  },
};

// ===== Filter Configuration (OCP: extend by adding entries) =====

export const STATUS_FILTER_OPTIONS: StatusFilterOption[] = ["all", "no_idea", "pending_launch"];

export const STATUS_FILTER_CONFIG: Record<StatusFilterOption, StatusFilterConfig> = {
  all: { label: "All", activeClass: "bg-slate-500/15 text-slate-300" },
  no_idea: { label: "No idea", activeClass: "bg-slate-500/15 text-slate-400" },
  pending_launch: {
    label: "Pending",
    activeClass: "bg-amber-500/15 text-amber-400",
  },
  in_research: {
    label: "Running",
    activeClass: "bg-sky-500/15 text-sky-400",
  },
  completed: {
    label: "Completed",
    activeClass: "bg-emerald-500/15 text-emerald-400",
  },
  failed: { label: "Failed", activeClass: "bg-red-500/15 text-red-400" },
};

// ===== Status Derivation =====

/**
 * Derives idea status from Conversation fields
 * MVP: Based on ideaTitle/ideaAbstract presence
 * Future: Will use backend-provided status
 */
export function deriveIdeaStatus(conversation: Conversation): IdeaStatus {
  // Check if conversation has an idea
  if (!conversation.ideaTitle && !conversation.ideaAbstract) {
    return "no_idea";
  }

  // MVP: Default to pending_launch for conversations with ideas
  // Future: Check conversation.latestResearchStatus when available
  return "pending_launch";
}

// ===== Badge Rendering =====

/**
 * Returns a styled status badge for an idea status
 * @param status - Idea status
 * @returns React element with styled badge
 */
export function getIdeaStatusBadge(status: IdeaStatus): ReactNode {
  const config = IDEA_STATUS_CONFIG[status];
  const Icon = config.icon;
  const isSpinning = status === "in_research";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium ${config.className}`}
    >
      <Icon className={`h-3.5 w-3.5 ${isSpinning ? "animate-spin" : ""}`} />
      {config.label}
    </span>
  );
}

// ===== Text Utilities =====

/**
 * Truncates text to a maximum length with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length (default: 200)
 * @returns Truncated text with ellipsis if needed
 */
export function truncateText(text: string, maxLength = 200): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trim()}...`;
}
