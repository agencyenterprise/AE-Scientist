"use client";

import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Download,
  HelpCircle,
  Loader2,
  ThumbsDown,
  ThumbsUp,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import type { components } from "@/types/api.gen";

import { fetchPaperDownloadUrl } from "../api";

type PaperReviewDetail = components["schemas"]["PaperReviewDetail"];
type ReviewScoreKey =
  | "originality"
  | "quality"
  | "clarity"
  | "significance"
  | "soundness"
  | "presentation"
  | "contribution"
  | "overall"
  | "confidence";

interface PaperReviewResultProps {
  review: PaperReviewDetail;
}

interface ScoreMetric {
  label: string;
  key: ReviewScoreKey;
  max: number;
}

const SCORE_METRICS: ScoreMetric[] = [
  { label: "Originality", key: "originality", max: 4 },
  { label: "Quality", key: "quality", max: 4 },
  { label: "Clarity", key: "clarity", max: 4 },
  { label: "Significance", key: "significance", max: 4 },
  { label: "Soundness", key: "soundness", max: 4 },
  { label: "Presentation", key: "presentation", max: 4 },
  { label: "Contribution", key: "contribution", max: 4 },
  { label: "Overall", key: "overall", max: 10 },
  { label: "Confidence", key: "confidence", max: 5 },
];

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

function getScoreLabel(key: ReviewScoreKey, score: number): string {
  switch (key) {
    case "originality":
    case "quality":
    case "clarity":
    case "significance":
      return LABELS_LOW_TO_HIGH[score] || "";
    case "soundness":
    case "presentation":
    case "contribution":
      return LABELS_POOR_TO_EXCELLENT[score] || "";
    case "overall":
      return LABELS_OVERALL[score] || "";
    case "confidence":
      return LABELS_CONFIDENCE[score] || "";
    default:
      return "";
  }
}

function getScoreColor(score: number, max: number): string {
  const ratio = score / max;
  if (ratio >= 0.75) return "text-emerald-400";
  if (ratio >= 0.5) return "text-amber-400";
  return "text-red-400";
}

function getDecisionColor(decision: string): string {
  const d = decision.toLowerCase();
  if (d.includes("accept"))
    return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  if (d.includes("reject"))
    return "text-red-400 bg-red-500/10 border-red-500/30";
  return "text-amber-400 bg-amber-500/10 border-amber-500/30";
}

function getDecisionIcon(decision: string) {
  const d = decision.toLowerCase();
  if (d.includes("accept")) return <CheckCircle className="h-5 w-5" />;
  if (d.includes("reject")) return <XCircle className="h-5 w-5" />;
  return <HelpCircle className="h-5 w-5" />;
}

function ScoreBadge({
  score,
  label,
  max,
  semanticLabel,
}: {
  score: number | null;
  label: string;
  max: number;
  semanticLabel: string;
}) {
  if (score === null) return null;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-2 text-center sm:p-3">
      <div className="mb-1 text-[10px] text-slate-400 sm:text-xs">{label}</div>
      <div
        className={`text-lg font-bold sm:text-xl ${getScoreColor(score, max)}`}
      >
        {score}
        <span className="text-xs font-normal text-slate-500 sm:text-sm">
          /{max}
        </span>
      </div>
      {semanticLabel && (
        <div className="mt-1 hidden text-xs text-slate-500 sm:block">
          {semanticLabel}
        </div>
      )}
    </div>
  );
}

function CollapsibleSection({
  title,
  icon,
  items,
  bulletColor,
  defaultOpen = true,
}: {
  title: string;
  icon: React.ReactNode;
  items: string[] | null | undefined;
  bulletColor: string;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!items || items.length === 0) return null;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between p-3 text-left sm:p-4"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium text-white sm:text-base">
            {title}
          </span>
        </div>
        {isOpen ? (
          <ChevronUp className="h-5 w-5 shrink-0 text-slate-400" />
        ) : (
          <ChevronDown className="h-5 w-5 shrink-0 text-slate-400" />
        )}
      </button>
      {isOpen && (
        <div className="border-t border-slate-700 p-3 sm:p-4">
          <ul className="space-y-2">
            {items.map((item, index) => (
              <li key={index} className="flex gap-2 text-sm text-slate-300">
                <span
                  className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${bulletColor}`}
                />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function PaperReviewResult({ review }: PaperReviewResultProps) {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const result = await fetchPaperDownloadUrl(review.id);
      window.open(result.download_url, "_blank");
    } catch {
      // Ignore errors
    } finally {
      setIsDownloading(false);
    }
  };

  if (review.status === "failed") {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 sm:p-6">
        <div className="flex items-start gap-2 sm:gap-3">
          <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400 sm:h-6 sm:w-6" />
          <div>
            <h3 className="mb-1 text-base font-medium text-red-400 sm:text-lg">
              Review Failed
            </h3>
            <p className="text-sm text-slate-300 sm:text-base">
              {review.error_message ||
                "An error occurred while processing your paper."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Decision Banner */}
      {review.decision && (
        <div
          className={`flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4 ${getDecisionColor(review.decision)}`}
        >
          <div className="flex items-center gap-3">
            {getDecisionIcon(review.decision)}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold capitalize">
                  {review.decision}
                </span>
                {review.overall !== null && review.overall !== undefined && (
                  <>
                    <span className="opacity-50">·</span>
                    <span className="text-lg font-bold">
                      {review.overall}/10
                    </span>
                    <span className="text-sm opacity-70">
                      ({LABELS_OVERALL[review.overall]})
                    </span>
                  </>
                )}
              </div>
              <div className="text-sm opacity-80">
                {review.original_filename}
              </div>
            </div>
          </div>
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-current px-3 py-1.5 text-sm transition-opacity hover:opacity-80 disabled:opacity-50 sm:w-auto"
            title="Download original paper"
          >
            {isDownloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            <span>Download PDF</span>
          </button>
        </div>
      )}

      {/* Summary */}
      {review.summary && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 sm:p-4">
          <h3 className="mb-2 font-medium text-white sm:mb-3">Summary</h3>
          <p className="text-sm leading-relaxed text-slate-300">
            {review.summary}
          </p>
        </div>
      )}

      {/* Scores Grid */}
      <div>
        <h3 className="mb-2 font-medium text-white sm:mb-3">
          Quantitative Scores
        </h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-5">
          {SCORE_METRICS.map((metric) => {
            const score = review[metric.key] as number | null;
            const semanticLabel =
              score !== null ? getScoreLabel(metric.key, score) : "";
            return (
              <ScoreBadge
                key={metric.key}
                score={score}
                label={metric.label}
                max={metric.max}
                semanticLabel={semanticLabel}
              />
            );
          })}
        </div>
      </div>

      {/* Collapsible Sections */}
      <div className="space-y-3">
        <CollapsibleSection
          title={`Strengths (${review.strengths?.length || 0})`}
          icon={<ThumbsUp className="h-5 w-5 text-emerald-400" />}
          items={review.strengths}
          bulletColor="bg-emerald-400"
          defaultOpen={true}
        />
        <CollapsibleSection
          title={`Weaknesses (${review.weaknesses?.length || 0})`}
          icon={<ThumbsDown className="h-5 w-5 text-red-400" />}
          items={review.weaknesses}
          bulletColor="bg-red-400"
          defaultOpen={true}
        />
        <CollapsibleSection
          title={`Questions (${review.questions?.length || 0})`}
          icon={<HelpCircle className="h-5 w-5 text-sky-400" />}
          items={review.questions}
          bulletColor="bg-sky-400"
          defaultOpen={false}
        />
        <CollapsibleSection
          title={`Limitations (${review.limitations?.length || 0})`}
          icon={<AlertTriangle className="h-5 w-5 text-amber-400" />}
          items={review.limitations}
          bulletColor="bg-amber-400"
          defaultOpen={false}
        />
      </div>

      {/* Ethical Concerns */}
      {review.ethical_concerns && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-red-400 sm:p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <span className="text-sm font-medium">
              Ethical concerns were identified in this paper
            </span>
          </div>
          {review.ethical_concerns_explanation && (
            <p className="mt-2 text-sm text-red-300">
              {review.ethical_concerns_explanation}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
