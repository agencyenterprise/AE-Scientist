"use client";

import { cn } from "@/shared/lib/utils";
import type { LlmReviewResponse } from "@/types/research";

interface AutoEvaluationCardProps {
  review: LlmReviewResponse | null;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  onViewDetails?: () => void;
  disabled?: boolean;
}

/**
 * Configuration for verdict display
 * Maps decision values to display labels and styling
 */
const VERDICT_CONFIG = {
  Accept: {
    label: "PASS",
    className: "text-emerald-400",
  },
  Reject: {
    label: "FAIL",
    className: "text-red-400",
  },
} as const;

/**
 * Configuration for decision display
 */
const DECISION_CONFIG = {
  Accept: {
    className: "text-emerald-400",
  },
  Reject: {
    className: "text-red-400",
  },
} as const;

type DecisionKey = keyof typeof VERDICT_CONFIG;

function isValidDecision(decision: string): decision is DecisionKey {
  return decision === "Accept" || decision === "Reject";
}

/**
 * AutoEvaluationCard Component
 *
 * Displays a summary of the auto-evaluation results with:
 * - Verdict (PASS/FAIL)
 * - Overall score (X/10)
 * - Decision (Accept/Reject)
 * - View Details button to open the full modal
 *
 * States:
 * - Loading: Shows loading indicator
 * - Not Found: Shows "No evaluation" message
 * - Error: Shows error state
 * - Loaded: Shows evaluation summary with metrics
 *
 * @param review - The LlmReviewResponse object (null while loading/not found)
 * @param loading - Whether data is currently being loaded
 * @param notFound - Whether no review exists for this run
 * @param error - Error message if loading failed
 * @param onViewDetails - Callback when View Details button is clicked
 * @param disabled - Whether the card interactions are disabled
 */
export function AutoEvaluationCard({
  review,
  loading,
  notFound,
  error,
  onViewDetails,
  disabled = false,
}: AutoEvaluationCardProps) {
  const hasReview = review !== null;
  const showLoading = loading && !hasReview;
  const showNotFound = notFound && !hasReview && !loading;
  const showError = error && !hasReview && !loading;
  const showContent = hasReview && !loading;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 w-full p-6">
      <h3 className="text-lg font-semibold text-white mb-4">Evaluation</h3>

      {showLoading && (
        <div className="flex items-center justify-between">
          <div className="flex gap-8">
            <div className="animate-pulse">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                Verdict
              </div>
              <div className="h-7 w-12 bg-slate-700 rounded" />
            </div>
            <div className="animate-pulse">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                Overall
              </div>
              <div className="h-7 w-12 bg-slate-700 rounded" />
            </div>
            <div className="animate-pulse">
              <div className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                Decision
              </div>
              <div className="h-7 w-16 bg-slate-700 rounded" />
            </div>
          </div>
          {onViewDetails && (
            <button
              disabled
              className="px-4 py-2 text-sm font-medium border border-slate-700 rounded-full text-slate-400 opacity-50"
            >
              Loading...
            </button>
          )}
        </div>
      )}

      {showNotFound && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-400">No evaluation available for this run</p>
        </div>
      )}

      {showError && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-red-400">Couldn&apos;t load evaluation</p>
          {onViewDetails && (
            <button
              onClick={onViewDetails}
              disabled={disabled}
              className="px-4 py-2 text-sm font-medium border border-slate-700 rounded-full text-white hover:bg-slate-800 transition disabled:opacity-50"
            >
              Retry
            </button>
          )}
        </div>
      )}

      {showContent && (
        <div className="flex items-center justify-between">
          <div className="flex gap-8">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                Verdict
              </div>
              <div
                className={cn(
                  "text-2xl font-bold",
                  isValidDecision(review.decision)
                    ? VERDICT_CONFIG[review.decision].className
                    : "text-slate-400"
                )}
              >
                {isValidDecision(review.decision) ? VERDICT_CONFIG[review.decision].label : "—"}
              </div>
            </div>

            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                Overall
              </div>
              <div className="text-2xl font-bold text-yellow-300">
                {review.overall}
                <span className="text-sm text-slate-400 font-normal">/10</span>
              </div>
            </div>

            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-1">
                Decision
              </div>
              <div
                className={cn(
                  "text-2xl font-bold",
                  isValidDecision(review.decision)
                    ? DECISION_CONFIG[review.decision].className
                    : "text-slate-400"
                )}
              >
                {review.decision}
              </div>
            </div>
          </div>

          {onViewDetails && (
            <button
              onClick={onViewDetails}
              disabled={disabled}
              className="px-4 py-2 text-sm font-medium border border-slate-700 rounded-full text-white hover:bg-slate-800 transition disabled:opacity-50"
            >
              View Details
            </button>
          )}
        </div>
      )}
    </div>
  );
}
