"use client";

import { AlertCircle, Cpu, CheckCircle, XCircle } from "lucide-react";
import { ProgressBar } from "@/shared/components/ui/progress-bar";
import { Markdown } from "@/shared/components/Markdown";
import { getStageBadge } from "../utils/research-utils";

export interface ResearchBoardCardBodyProps {
  ideaTitle: string;
  ideaMarkdown: string | null; // Full idea content in markdown format
  status: string;
  errorMessage: string | null;
  currentStage: string | null;
  progress: number | null;
  gpuType: string;
  evaluationOverall: number | null;
  evaluationDecision: string | null;
}

/**
 * Truncate text to a maximum length, ensuring we don't cut in the middle of a word
 */
function truncateText(text: string, maxLength: number = 500): string {
  if (text.length <= maxLength) {
    return text;
  }

  // Find the last space before maxLength
  const truncated = text.slice(0, maxLength);
  const lastSpaceIndex = truncated.lastIndexOf(" ");

  if (lastSpaceIndex > 0) {
    return truncated.slice(0, lastSpaceIndex) + "...";
  }

  return truncated + "...";
}

export function ResearchBoardCardBody({
  ideaTitle,
  ideaMarkdown,
  status,
  errorMessage,
  currentStage,
  progress,
  gpuType,
  evaluationOverall,
  evaluationDecision,
}: ResearchBoardCardBodyProps) {
  // Truncate the markdown for card display
  const truncatedMarkdown = ideaMarkdown ? truncateText(ideaMarkdown, 500) : null;
  const hasEvaluation = evaluationOverall !== null && evaluationDecision !== null;
  const isAccepted = evaluationDecision === "Accept";

  return (
    <div className="p-4 sm:p-5">
      {/* Title */}
      <h3 className="text-base font-semibold text-white sm:text-lg">{ideaTitle}</h3>

      {/* Markdown Content */}
      {truncatedMarkdown && (
        <div className="mt-2 text-sm leading-relaxed text-slate-400 prose-sm prose-invert max-w-none line-clamp-3 sm:line-clamp-none [&_p]:my-1 [&_h1]:hidden [&_h2]:hidden [&_h3]:hidden [&_h4]:hidden [&_h5]:hidden [&_h6]:hidden [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5">
          <Markdown>{truncatedMarkdown}</Markdown>
        </div>
      )}

      {/* Error Message for Failed Runs */}
      {status === "failed" && errorMessage && (
        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 sm:mt-4 sm:p-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
            <p className="text-sm text-red-300 line-clamp-2">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:mt-5 sm:grid-cols-4 sm:gap-4">
        {/* Stage */}
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
            Stage
          </p>
          {getStageBadge(currentStage, status) || (
            <span className="text-sm text-slate-500">Not started</span>
          )}
        </div>

        {/* Progress */}
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
            Progress
          </p>
          <ProgressBar progress={progress} />
        </div>

        {/* GPU */}
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">GPU</p>
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-slate-500" />
            <span className="text-sm text-slate-300">{gpuType || "Not assigned"}</span>
          </div>
        </div>

        {/* Evaluation */}
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-slate-500">
            Evaluation
          </p>
          {hasEvaluation ? (
            <div
              className={`flex items-center gap-2 ${
                isAccepted ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {isAccepted ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
              <span className="text-sm font-medium">{isAccepted ? "PASS" : "FAIL"}</span>
              <span className="text-sm text-slate-400">({evaluationOverall}/10)</span>
            </div>
          ) : (
            <span className="text-sm text-slate-500">—</span>
          )}
        </div>
      </div>
    </div>
  );
}
