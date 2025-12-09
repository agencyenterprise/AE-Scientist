"use client";

import { cn } from "@/shared/lib/utils";

/**
 * Status type for conversations
 * - "draft": Conversation without research
 * - "with_research": Conversation with research runs
 */
export type ConversationStatus = "draft" | "with_research";

interface ConversationStatusBadgeProps {
  status: ConversationStatus;
}

/**
 * Configuration for conversation status badges
 * Maps status values to display labels and styling
 */
const STATUS_CONFIG = {
  draft: {
    label: "Draft",
    className: "bg-slate-700/50 text-slate-400 border border-slate-600/30",
  },
  with_research: {
    label: "Researched",
    className: "bg-sky-500/15 text-sky-400 border border-sky-500/30",
  },
} as const;

/**
 * ConversationStatusBadge Component
 *
 * Displays the status of a conversation as a small badge.
 * - Draft: Gray badge for conversations without research
 * - Researched: Blue badge for conversations with active research
 *
 * Styling:
 * - Text: 10px, medium weight, uppercase with wide letter spacing
 * - Padding: Compact (px-2 py-0.5) to maintain small visual footprint
 * - Colors: Status-dependent with subtle borders for definition
 *
 * @param status - The conversation status ("draft" or "with_research")
 */
export function ConversationStatusBadge({ status }: ConversationStatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5 shrink-0",
        "text-[10px] font-medium uppercase tracking-wide",
        config.className
      )}
    >
      {config.label}
    </span>
  );
}
