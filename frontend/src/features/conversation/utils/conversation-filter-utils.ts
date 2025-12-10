import type {
  ConversationStatusFilter,
  RunStatusFilter,
  FilterConfig,
} from "../types/conversation-filter.types";

export const CONVERSATION_STATUS_OPTIONS: ConversationStatusFilter[] = [
  "all",
  "draft",
  "with_research",
];

export const CONVERSATION_STATUS_FILTER_CONFIG: Record<ConversationStatusFilter, FilterConfig> = {
  all: { label: "All", activeClass: "bg-slate-500/15 text-slate-300" },
  draft: { label: "Draft", activeClass: "bg-amber-500/15 text-amber-400" },
  with_research: { label: "Researched", activeClass: "bg-emerald-500/15 text-emerald-400" },
};

export const RUN_STATUS_OPTIONS: RunStatusFilter[] = [
  "all",
  "pending",
  "running",
  "completed",
  "failed",
];

export const RUN_STATUS_FILTER_CONFIG: Record<RunStatusFilter, FilterConfig> = {
  all: { label: "All", activeClass: "bg-slate-500/15 text-slate-300" },
  pending: { label: "Pending", activeClass: "bg-amber-500/15 text-amber-400" },
  running: { label: "Running", activeClass: "bg-sky-500/15 text-sky-400" },
  completed: { label: "Completed", activeClass: "bg-emerald-500/15 text-emerald-400" },
  failed: { label: "Failed", activeClass: "bg-red-500/15 text-red-400" },
};
