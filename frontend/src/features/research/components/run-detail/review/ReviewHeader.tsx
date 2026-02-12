"use client";

import { X, Download } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { downloadEvaluationMarkdown } from "@/features/research/utils/evaluation-download";
import type { LlmReviewResponse } from "@/types/research";

interface ReviewHeaderProps {
  review: LlmReviewResponse;
  onClose: () => void;
}

/**
 * Configuration for verdict badges
 * Maps decision values to display labels and styling
 */
const VERDICT_CONFIG = {
  Accept: {
    label: "PASS",
    className: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
  },
  Reject: {
    label: "FAIL",
    className: "bg-red-500/15 text-red-400 border border-red-500/30",
  },
} as const;

type DecisionKey = keyof typeof VERDICT_CONFIG;

function isValidDecision(decision: string): decision is DecisionKey {
  return decision === "Accept" || decision === "Reject";
}

/**
 * ReviewHeader Component
 *
 * Displays the modal title and verdict badge at the top of the review modal.
 * Shows the auto-evaluation decision (Accept/Reject) as PASS/FAIL.
 *
 * @param review - The full review object
 * @param onClose - Callback function when close button is clicked
 */
export function ReviewHeader({ review, onClose }: ReviewHeaderProps) {
  const config = isValidDecision(review.decision)
    ? VERDICT_CONFIG[review.decision]
    : { label: "—", className: "bg-slate-500/15 text-slate-400 border border-slate-500/30" };

  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3">
        <h2 id="modal-title" className="text-xl font-semibold text-foreground">
          Evaluation Details
        </h2>
        <span
          className={cn(
            "px-2 py-1 text-[10px] font-medium uppercase tracking-wide rounded",
            config.className
          )}
        >
          {config.label}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => downloadEvaluationMarkdown(review)}
          className="text-muted-foreground hover:text-foreground transition"
          aria-label="Download as markdown"
          title="Download as markdown"
        >
          <Download className="h-5 w-5" />
        </button>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition"
          aria-label="Close modal"
        >
          <X className="h-6 w-6" />
        </button>
      </div>
    </div>
  );
}
