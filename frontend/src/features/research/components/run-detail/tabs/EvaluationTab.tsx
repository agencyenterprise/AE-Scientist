"use client";

import { useState } from "react";
import { AutoEvaluationCard } from "../AutoEvaluationCard";
import type { LlmReviewResponse } from "@/types/research";
import { cn } from "@/shared/lib/utils";
import { FileText, ThumbsUp, ThumbsDown, HelpCircle, AlertTriangle, ChevronDown } from "lucide-react";

// Label mappings for scores
const LABELS_LOW_TO_HIGH: Record<number, string> = {
  1: "Low",
  2: "Medium",
  3: "High",
  4: "Very high",
};

const LABELS_POOR_TO_EXCELLENT: Record<number, string> = {
  1: "Poor",
  2: "Fair",
  3: "Good",
  4: "Excellent",
};

const LABELS_OVERALL: Record<number, string> = {
  1: "Very Strong Reject",
  2: "Strong Reject",
  3: "Reject",
  4: "Borderline Reject",
  5: "Borderline Accept",
  6: "Weak Accept",
  7: "Accept",
  8: "Strong Accept",
  9: "Very Strong Accept",
  10: "Award Quality",
};

const LABELS_CONFIDENCE: Record<number, string> = {
  1: "Educated guess",
  2: "Uncertain",
  3: "Fairly confident",
  4: "Confident",
  5: "Absolutely certain",
};

type ScoreType = "low_to_high" | "poor_to_excellent" | "overall" | "confidence";

function getScoreLabel(type: ScoreType, score: number): string {
  switch (type) {
    case "low_to_high":
      return LABELS_LOW_TO_HIGH[score] || "";
    case "poor_to_excellent":
      return LABELS_POOR_TO_EXCELLENT[score] || "";
    case "overall":
      return LABELS_OVERALL[score] || "";
    case "confidence":
      return LABELS_CONFIDENCE[score] || "";
    default:
      return "";
  }
}

// Get score color based on normalized value (0-1)
function getScoreColor(normalized: number): { text: string; bg: string; ring: string } {
  if (normalized >= 0.8) return { text: "text-emerald-400", bg: "bg-emerald-400", ring: "ring-emerald-400/30" };
  if (normalized >= 0.6) return { text: "text-teal-400", bg: "bg-teal-400", ring: "ring-teal-400/30" };
  if (normalized >= 0.4) return { text: "text-amber-400", bg: "bg-amber-400", ring: "ring-amber-400/30" };
  return { text: "text-red-400", bg: "bg-red-400", ring: "ring-red-400/30" };
}

interface EvaluationTabProps {
  review: LlmReviewResponse | null;
  reviewLoading: boolean;
  reviewNotFound: boolean;
  reviewError: string | null;
  conversationId: number | null;
}

export function EvaluationTab({
  review,
  reviewLoading,
  reviewNotFound,
  reviewError,
  conversationId,
}: EvaluationTabProps) {
  return (
    <div className="flex flex-col gap-6">
      <AutoEvaluationCard
        review={review}
        loading={reviewLoading}
        notFound={reviewNotFound}
        error={reviewError}
        disabled={conversationId === null}
      />

      {review && (
        <DetailedScoresSection review={review} />
      )}

      {review?.summary && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 w-full p-4 sm:p-6">
          <div className="mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5 text-slate-400" />
            <h2 className="text-lg font-semibold text-white">Summary</h2>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed">{review.summary}</p>
        </div>
      )}

      {review && (review.strengths.length > 0 || review.weaknesses.length > 0) && (
        <div className="grid gap-4 sm:gap-6 md:grid-cols-2">
          {review.strengths.length > 0 && (
            <div className="rounded-2xl border border-emerald-500/20 bg-slate-900/50 w-full p-4 sm:p-6">
              <div className="mb-4 flex items-center gap-2">
                <ThumbsUp className="h-5 w-5 text-emerald-400" />
                <h2 className="text-lg font-semibold text-emerald-400">Strengths</h2>
              </div>
              <ul className="flex flex-col gap-2">
                {review.strengths.map((strength, idx) => (
                  <li key={idx} className="text-sm text-slate-300">
                    • {strength}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {review.weaknesses.length > 0 && (
            <div className="rounded-2xl border border-red-500/20 bg-slate-900/50 w-full p-4 sm:p-6">
              <div className="mb-4 flex items-center gap-2">
                <ThumbsDown className="h-5 w-5 text-red-400" />
                <h2 className="text-lg font-semibold text-red-400">Weaknesses</h2>
              </div>
              <ul className="flex flex-col gap-2">
                {review.weaknesses.map((weakness, idx) => (
                  <li key={idx} className="text-sm text-slate-300">
                    • {weakness}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {review && (review.questions.length > 0 || review.limitations.length > 0) && (
        <div className="grid gap-4 sm:gap-6 md:grid-cols-2">
          {review.questions.length > 0 && (
            <div className="rounded-2xl border border-sky-500/20 bg-slate-900/50 w-full p-4 sm:p-6">
              <div className="mb-4 flex items-center gap-2">
                <HelpCircle className="h-5 w-5 text-sky-400" />
                <h2 className="text-lg font-semibold text-sky-400">Questions</h2>
              </div>
              <ul className="flex flex-col gap-2">
                {review.questions.map((question, idx) => (
                  <li key={idx} className="text-sm text-slate-300">
                    • {question}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {review.limitations.length > 0 && (
            <div className="rounded-2xl border border-slate-500/20 bg-slate-900/50 w-full p-4 sm:p-6">
              <div className="mb-4 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-slate-400" />
                <h2 className="text-lg font-semibold text-slate-400">Limitations</h2>
              </div>
              <ul className="flex flex-col gap-2">
                {review.limitations.map((limitation, idx) => (
                  <li key={idx} className="text-sm text-slate-300">
                    • {limitation}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DetailedScoresSection({ review }: { review: LlmReviewResponse }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 w-full p-4 sm:p-6">
      {/* Overall Score - Always visible */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex items-center gap-4">
          <div className="relative">
            <svg className="w-16 h-16 sm:w-20 sm:h-20 -rotate-90" viewBox="0 0 36 36">
              <circle
                cx="18"
                cy="18"
                r="15.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                className="text-slate-800"
              />
              <circle
                cx="18"
                cy="18"
                r="15.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeDasharray={`${(review.overall / 10) * 97.4} 97.4`}
                strokeLinecap="round"
                className={cn(
                  review.overall >= 7 ? "text-emerald-400" :
                  review.overall >= 5 ? "text-amber-400" : "text-red-400"
                )}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className={cn(
                "text-lg sm:text-xl font-bold",
                review.overall >= 7 ? "text-emerald-400" :
                review.overall >= 5 ? "text-amber-400" : "text-red-400"
              )}>
                {review.overall}
              </span>
            </div>
          </div>
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider">Overall Score</p>
            <p className={cn(
              "text-base sm:text-lg font-semibold",
              review.overall >= 7 ? "text-emerald-400" :
              review.overall >= 5 ? "text-amber-400" : "text-red-400"
            )}>
              {getScoreLabel("overall", review.overall)}
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              Confidence: {review.confidence}/5 · {getScoreLabel("confidence", review.confidence)}
            </p>
          </div>
        </div>

        {/* Mobile: Toggle button for category scores */}
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="sm:hidden flex items-center justify-center gap-2 mt-2 px-3 py-2 rounded-lg bg-slate-800/50 text-sm text-slate-400 hover:text-slate-300 transition-colors"
        >
          <span>{isExpanded ? "Hide" : "Show"} category scores</span>
          <ChevronDown className={cn("h-4 w-4 transition-transform", isExpanded && "rotate-180")} />
        </button>
      </div>

      {/* Category Scores - Collapsible on mobile, always visible on desktop */}
      <div className={cn(
        "mt-5 pt-5 border-t border-slate-800",
        "sm:block", // Always visible on sm+
        isExpanded ? "block" : "hidden" // Toggle on mobile
      )}>
        <div className="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-4">
          <ScoreItem
            label="Originality"
            value={review.originality}
            maxValue={4}
            semanticLabel={getScoreLabel("low_to_high", review.originality)}
          />
          <ScoreItem
            label="Quality"
            value={review.quality}
            maxValue={4}
            semanticLabel={getScoreLabel("low_to_high", review.quality)}
          />
          <ScoreItem
            label="Clarity"
            value={review.clarity}
            maxValue={4}
            semanticLabel={getScoreLabel("low_to_high", review.clarity)}
          />
          <ScoreItem
            label="Significance"
            value={review.significance}
            maxValue={4}
            semanticLabel={getScoreLabel("low_to_high", review.significance)}
          />
          <ScoreItem
            label="Soundness"
            value={review.soundness}
            maxValue={4}
            semanticLabel={getScoreLabel("poor_to_excellent", review.soundness)}
          />
          <ScoreItem
            label="Presentation"
            value={review.presentation}
            maxValue={4}
            semanticLabel={getScoreLabel("poor_to_excellent", review.presentation)}
          />
          <ScoreItem
            label="Contribution"
            value={review.contribution}
            maxValue={4}
            semanticLabel={getScoreLabel("poor_to_excellent", review.contribution)}
          />
        </div>
      </div>
    </div>
  );
}

function ScoreItem({
  label,
  value,
  maxValue = 4,
  semanticLabel,
}: {
  label: string;
  value: number;
  maxValue?: number;
  semanticLabel?: string;
}) {
  const normalized = value / maxValue;
  const colors = getScoreColor(normalized);

  return (
    <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/50">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-slate-400 font-medium">{label}</p>
        <p className={cn("text-sm font-semibold tabular-nums", colors.text)}>
          {value}<span className="text-slate-500 font-normal">/{maxValue}</span>
        </p>
      </div>
      <div className="h-1.5 rounded-full bg-slate-700/50 overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", colors.bg)}
          style={{ width: `${normalized * 100}%` }}
        />
      </div>
      {semanticLabel && (
        <p className="mt-1.5 text-xs text-slate-500">{semanticLabel}</p>
      )}
    </div>
  );
}
