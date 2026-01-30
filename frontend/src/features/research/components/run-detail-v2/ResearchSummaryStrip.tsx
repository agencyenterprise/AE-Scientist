"use client";

import { cn } from "@/shared/lib/utils";
import { getCurrentStageLabel } from "../../utils/research-utils";
import type { LlmReviewResponse } from "@/types/research";
import { CheckCircle2, XCircle, Loader2, AlertCircle } from "lucide-react";

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

  return (
    <div className="flex flex-wrap items-center gap-y-3 rounded-xl border border-slate-800 bg-slate-900/50 px-6 py-5">
      <div className="flex flex-1 justify-center">
        <div className="flex flex-col items-start">
          <span className="text-xs font-medium text-slate-400">Status</span>
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <span className="text-sm font-semibold text-white">{currentStageLabel}</span>
          </div>
        </div>
      </div>

      <div className="hidden h-10 w-px bg-slate-700 sm:block" />

      <div className="flex flex-1 justify-center">
        <div className="flex flex-col items-start">
          <span className="text-xs font-medium text-slate-400">Progress</span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white">
              {progressPercent !== null ? `${progressPercent}%` : "-"}
            </span>
            {progressPercent !== null && (
              <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-700">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="hidden h-10 w-px bg-slate-700 sm:block" />

      <div className="flex flex-1 justify-center">
        <div className="flex flex-col items-start">
          <span className="text-xs font-medium text-slate-400">Duration</span>
          <span className="text-sm font-semibold text-white">{formatDuration()}</span>
        </div>
      </div>

      <div className="hidden h-10 w-px bg-slate-700 sm:block" />

      <div className="flex flex-1 justify-center">
        <div className="flex flex-col items-start">
          <span className="text-xs font-medium text-slate-400">Evaluation</span>
          {reviewLoading ? (
            <span className="text-sm text-slate-400">Loading...</span>
          ) : review ? (
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "text-sm font-bold",
                  review.decision === "Accept" ? "text-emerald-400" : "text-red-400"
                )}
              >
                {review.decision === "Accept" ? "PASS" : "FAIL"}
              </span>
              <span className="text-sm font-semibold text-yellow-400">{review.overall}/10</span>
            </div>
          ) : (
            <span className="text-sm text-slate-400">-</span>
          )}
        </div>
      </div>

      <div className="hidden h-10 w-px bg-slate-700 sm:block" />

      <div className="flex flex-1 justify-center">
        <div className="flex flex-col items-start">
          <span className="text-xs font-medium text-slate-400">Total Cost</span>
          <span className="text-sm font-semibold text-white">
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
