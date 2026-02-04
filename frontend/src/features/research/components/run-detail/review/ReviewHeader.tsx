"use client";

import { X, Download } from "lucide-react";
import { cn } from "@/shared/lib/utils";
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
 * Generates markdown content from the review data
 */
function generateMarkdown(review: LlmReviewResponse): string {
  const verdict = review.decision === "Accept" ? "PASS" : "FAIL";
  const lines: string[] = [];

  lines.push(`# Evaluation Details`);
  lines.push("");
  lines.push(`**Verdict:** ${verdict}`);
  lines.push(`**Decision:** ${review.decision}`);
  lines.push(`**Date:** ${new Date(review.created_at).toLocaleDateString()}`);
  lines.push("");

  // Scores section
  lines.push(`## Scores`);
  lines.push("");
  lines.push(`| Metric | Score |`);
  lines.push(`|--------|-------|`);
  lines.push(`| Originality | ${review.originality}/4 |`);
  lines.push(`| Quality | ${review.quality}/4 |`);
  lines.push(`| Clarity | ${review.clarity}/4 |`);
  lines.push(`| Significance | ${review.significance}/4 |`);
  lines.push(`| Soundness | ${review.soundness}/4 |`);
  lines.push(`| Presentation | ${review.presentation}/4 |`);
  lines.push(`| Contribution | ${review.contribution}/4 |`);
  lines.push(`| **Overall** | **${review.overall}/10** |`);
  lines.push(`| Confidence | ${review.confidence}/5 |`);
  lines.push("");

  // Analysis section
  lines.push(`## Analysis`);
  lines.push("");

  lines.push(`### Summary`);
  lines.push("");
  lines.push(review.summary);
  lines.push("");

  if (review.strengths.length > 0) {
    lines.push(`### Strengths`);
    lines.push("");
    review.strengths.forEach(s => lines.push(`- ${s}`));
    lines.push("");
  }

  if (review.weaknesses.length > 0) {
    lines.push(`### Weaknesses`);
    lines.push("");
    review.weaknesses.forEach(w => lines.push(`- ${w}`));
    lines.push("");
  }

  if (review.questions.length > 0) {
    lines.push(`### Questions`);
    lines.push("");
    review.questions.forEach(q => lines.push(`- ${q}`));
    lines.push("");
  }

  if (review.limitations.length > 0) {
    lines.push(`### Limitations`);
    lines.push("");
    review.limitations.forEach(l => lines.push(`- ${l}`));
    lines.push("");
  }

  if (review.ethical_concerns) {
    lines.push(`### Ethical Concerns`);
    lines.push("");
    lines.push(`This work has been flagged for potential ethical concerns.`);
    lines.push("");
  }

  return lines.join("\n");
}

/**
 * Downloads the review as a markdown file
 */
function downloadMarkdown(review: LlmReviewResponse) {
  const markdown = generateMarkdown(review);
  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `evaluation-${review.run_id}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
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
          onClick={() => downloadMarkdown(review)}
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
