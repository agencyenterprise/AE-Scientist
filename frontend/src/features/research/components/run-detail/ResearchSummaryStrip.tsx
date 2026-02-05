"use client";

import { cn } from "@/shared/lib/utils";
import { getCurrentStageLabel, TOOLTIP_EXPLANATIONS } from "../../utils/research-utils";
import type { LlmReviewResponse } from "@/types/research";
import { CheckCircle2, XCircle, Loader2, AlertCircle, HelpCircle } from "lucide-react";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/shared/components/ui/tooltip";

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

interface ResearchSummaryStripProps {
  status: string;
  currentStage: string | null;
  progress: number | null;
  review: LlmReviewResponse | null;
  reviewLoading: boolean;
  totalCost: number | null;
  isEstimatedCost: boolean;
  createdAt: string;
  updatedAt: string | null;
}

export function ResearchSummaryStrip({
  status,
  currentStage,
  progress,
  review,
  reviewLoading,
  totalCost,
  isEstimatedCost,
  createdAt,
  updatedAt,
}: ResearchSummaryStripProps) {
  const currentStageLabel = getCurrentStageLabel(status, currentStage, progress);
  const progressPercent =
    progress === null || progress === undefined ? null : Math.round(progress * 100);

  const formatCurrency = (amount: number | null) => {
    if (amount === null) return "-";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const startTime = new Date(createdAt);
  const endTime = updatedAt ? new Date(updatedAt) : new Date();
  const durationMs = endTime.getTime() - startTime.getTime();
  const durationMinutes = Math.floor(durationMs / 60000);
  const durationHours = Math.floor(durationMinutes / 60);
  const remainingMinutes = durationMinutes % 60;

  const formatDuration = () => {
    if (durationHours > 0) {
      return `${durationHours}h ${remainingMinutes}m`;
    }
    return `${durationMinutes}m`;
  };

  const getStatusIcon = () => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-400" />;
      case "running":
      case "initializing":
      case "pending":
        return <Loader2 className="h-4 w-4 text-yellow-400 animate-spin" />;
      default:
        return <AlertCircle className="h-4 w-4 text-slate-400" />;
    }
  };

  // Helper for tooltip labels
  const LabelWithTooltip = ({
    label,
    tooltipKey,
  }: {
    label: string;
    tooltipKey: keyof typeof TOOLTIP_EXPLANATIONS;
  }) => (
    <div className="flex items-center gap-1">
      <span className="text-xs font-medium text-slate-400">{label}</span>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="text-slate-500 hover:text-slate-400 transition-colors"
          >
            <HelpCircle className="h-3 w-3" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          className="max-w-xs bg-slate-800 text-slate-200 border-slate-700"
        >
          {TOOLTIP_EXPLANATIONS[tooltipKey]}
        </TooltipContent>
      </Tooltip>
    </div>
  );

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-3 sm:p-4 lg:p-5">
      {/* Mobile: Stack vertically, Desktop: Grid layout */}
      <div className="grid grid-cols-1 gap-3 xs:grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 sm:gap-4 lg:gap-6">
        {/* Status - Primary importance */}
        <div className="flex flex-col">
          <LabelWithTooltip label="Status" tooltipKey="stage" />
          <div className="flex items-center gap-2 mt-1">
            {getStatusIcon()}
            <span className="text-sm sm:text-base font-semibold text-white">{currentStageLabel}</span>
          </div>
        </div>

        {/* Progress */}
        <div className="flex flex-col">
          <LabelWithTooltip label="Progress" tooltipKey="progress" />
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm sm:text-base font-semibold text-white">
              {progressPercent !== null ? `${progressPercent}%` : "-"}
            </span>
          </div>
          {progressPercent !== null && (
            <div className="h-1.5 w-full max-w-20 sm:max-w-24 overflow-hidden rounded-full bg-slate-700 mt-1.5">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          )}
        </div>

        {/* Duration */}
        <div className="flex flex-col">
          <LabelWithTooltip label="Duration" tooltipKey="duration" />
          <span className="text-sm sm:text-base font-semibold text-white mt-1">{formatDuration()}</span>
        </div>

        {/* Evaluation - High importance, highlighted */}
        <div
          className={cn(
            "flex flex-col rounded-lg p-2 sm:p-3 -m-2 sm:-m-3",
            review && "bg-slate-800/50"
          )}
        >
          <LabelWithTooltip label="Evaluation" tooltipKey="evaluation" />
          {reviewLoading ? (
            <div className="flex items-center gap-2 mt-1">
              <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
              <span className="text-sm text-slate-400">Loading...</span>
            </div>
          ) : review ? (
            <div className="flex flex-col mt-1">
              <div className="flex items-center gap-2 sm:gap-3">
                <span
                  className={cn(
                    "text-lg sm:text-xl font-bold",
                    review.decision === "Accept" ? "text-emerald-400" : "text-red-400"
                  )}
                >
                  {review.decision === "Accept" ? "PASS" : "FAIL"}
                </span>
                <span className="text-base sm:text-lg font-semibold text-yellow-400">
                  {review.overall}
                  <span className="text-xs font-normal text-slate-400">/10</span>
                </span>
              </div>
              <span className="text-xs text-slate-500 mt-0.5">
                {LABELS_OVERALL[review.overall] || ""}
              </span>
            </div>
          ) : (
            <span className="text-sm text-slate-400 mt-1">-</span>
          )}
        </div>

        {/* Total Cost */}
        <div className="flex flex-col">
          <LabelWithTooltip label="Total Cost" tooltipKey="cost" />
          <span className="text-sm sm:text-base font-semibold text-white mt-1">
            {totalCost !== null ? (
              <>
                {formatCurrency(totalCost)}
                {isEstimatedCost && (
                  <span className="ml-1 text-xs font-normal text-slate-400">(est)</span>
                )}
              </>
            ) : (
              "-"
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
