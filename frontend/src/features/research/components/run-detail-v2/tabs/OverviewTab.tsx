"use client";

import { FinalPdfBanner } from "../../../components/run-detail/final-pdf-banner";
import { ImportSourceCard } from "../../../components/run-detail/import-source-card";
import { InitializationStatusBanner } from "../../../components/run-detail/initialization-status-banner";
import { ResearchRunError } from "../../../components/run-detail/research-run-error";
import { ResearchActivityFeed } from "../ResearchActivityFeed";
import type { ArtifactMetadata, LlmReviewResponse, ResearchRunInfo } from "@/types/research";
import { cn } from "@/shared/lib/utils";
import { ShieldCheck, ArrowRight, Loader2 } from "lucide-react";

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

interface OverviewTabProps {
  run: ResearchRunInfo;
  conversationId: number | null;
  runId: string;
  conversationUrl: string | null;
  artifacts: ArtifactMetadata[];
  review: LlmReviewResponse | null;
  reviewLoading: boolean;
  onViewEvaluation?: () => void;
}

export function OverviewTab({
  run,
  conversationId,
  runId,
  conversationUrl,
  artifacts,
  review,
  reviewLoading,
  onViewEvaluation,
}: OverviewTabProps) {
  const isCompleted = run.status === "completed" || run.status === "failed";

  return (
    <div className="flex flex-col gap-6">
      <InitializationStatusBanner
        status={run.status}
        initializationStatus={run.initialization_status}
      />

      {run.error_message && <ResearchRunError message={run.error_message} />}

      {conversationUrl && <ImportSourceCard conversationUrl={conversationUrl} />}

      {conversationId !== null && (
        <FinalPdfBanner artifacts={artifacts} conversationId={conversationId} runId={runId} />
      )}

      {isCompleted && (
        <EvaluationSummary
          review={review}
          loading={reviewLoading}
          onViewDetails={onViewEvaluation}
        />
      )}

      <ResearchActivityFeed runId={runId} maxHeight="600px" />
    </div>
  );
}

function EvaluationSummary({
  review,
  loading,
  onViewDetails,
}: {
  review: LlmReviewResponse | null;
  loading: boolean;
  onViewDetails?: () => void;
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck className="h-5 w-5 text-slate-400" />
          <h3 className="text-lg font-semibold text-white">Evaluation Summary</h3>
        </div>
        <div className="flex items-center justify-center py-4 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          <span>Loading evaluation...</span>
        </div>
      </div>
    );
  }

  if (!review) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck className="h-5 w-5 text-slate-400" />
          <h3 className="text-lg font-semibold text-white">Evaluation Summary</h3>
        </div>
        <p className="text-sm text-slate-400">No evaluation available for this run.</p>
      </div>
    );
  }

  const isAccepted = review.decision === "Accept";

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-slate-400" />
          <h3 className="text-lg font-semibold text-white">Evaluation Summary</h3>
        </div>
        {onViewDetails && (
          <button
            onClick={onViewDetails}
            className="flex items-center gap-1 text-sm text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            View full evaluation
            <ArrowRight className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-8 mb-4">
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Verdict</p>
          <p className={cn("text-2xl font-bold", isAccepted ? "text-emerald-400" : "text-red-400")}>
            {isAccepted ? "PASS" : "FAIL"}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Overall</p>
          <p className="text-2xl font-bold text-yellow-300">
            {review.overall}
            <span className="text-sm text-slate-400 font-normal">/10</span>
          </p>
          <p className="text-xs text-slate-500">{LABELS_OVERALL[review.overall] || ""}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Decision</p>
          <p className={cn("text-2xl font-bold", isAccepted ? "text-emerald-400" : "text-red-400")}>
            {review.decision}
          </p>
        </div>
      </div>

      {review.summary && (
        <div className="border-t border-slate-700 pt-4">
          <p className="text-sm text-slate-300 line-clamp-2">{review.summary}</p>
        </div>
      )}
    </div>
  );
}
