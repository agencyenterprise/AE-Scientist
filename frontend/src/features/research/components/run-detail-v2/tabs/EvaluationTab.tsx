"use client";

import { AutoEvaluationCard } from "../../../components/run-detail/AutoEvaluationCard";
import type { LlmReviewResponse } from "@/types/research";
import { cn } from "@/shared/lib/utils";
import { BarChart3, FileText, ThumbsUp, ThumbsDown, HelpCircle, AlertTriangle } from "lucide-react";

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
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
          <div className="mb-4 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-slate-400" />
            <h2 className="text-lg font-semibold text-white">Detailed Scores</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <ScoreItem label="Originality" value={review.originality} maxValue={4} />
            <ScoreItem label="Quality" value={review.quality} maxValue={4} />
            <ScoreItem label="Clarity" value={review.clarity} maxValue={4} />
            <ScoreItem label="Significance" value={review.significance} maxValue={4} />
            <ScoreItem label="Soundness" value={review.soundness} maxValue={4} />
            <ScoreItem label="Presentation" value={review.presentation} maxValue={4} />
            <ScoreItem label="Contribution" value={review.contribution} maxValue={4} />
            <ScoreItem label="Overall" value={review.overall} maxValue={10} />
            <ScoreItem label="Confidence" value={review.confidence} maxValue={5} />
          </div>
        </div>
      )}

      {review?.summary && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
          <div className="mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5 text-slate-400" />
            <h2 className="text-lg font-semibold text-white">Summary</h2>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed">{review.summary}</p>
        </div>
      )}

      {review && (review.strengths.length > 0 || review.weaknesses.length > 0) && (
        <div className="grid gap-6 lg:grid-cols-2">
          {review.strengths.length > 0 && (
            <div className="rounded-xl border border-emerald-500/20 bg-slate-900/50 w-full p-6">
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
            <div className="rounded-xl border border-red-500/20 bg-slate-900/50 w-full p-6">
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
        <div className="grid gap-6 lg:grid-cols-2">
          {review.questions.length > 0 && (
            <div className="rounded-xl border border-sky-500/20 bg-slate-900/50 w-full p-6">
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
            <div className="rounded-xl border border-slate-500/20 bg-slate-900/50 w-full p-6">
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

function ScoreItem({
  label,
  value,
  maxValue = 4,
}: {
  label: string;
  value: number;
  maxValue?: number;
}) {
  const normalizedScore = (value / maxValue) * 10;

  const getColorClass = (normalizedScore: number) => {
    if (normalizedScore >= 8) return "text-emerald-400";
    if (normalizedScore >= 6) return "text-yellow-400";
    if (normalizedScore >= 4) return "text-amber-400";
    return "text-red-400";
  };

  return (
    <div>
      <p className="text-xs text-slate-400 uppercase">{label}</p>
      <p className={cn("font-mono text-lg font-semibold", getColorClass(normalizedScore))}>
        {value}
        <span className="text-xs font-normal text-slate-400">/{maxValue}</span>
      </p>
    </div>
  );
}
