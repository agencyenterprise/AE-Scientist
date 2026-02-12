"use client";

import { useState } from "react";
import {
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Download,
  Loader2,
} from "lucide-react";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import type { components } from "@/types/api.gen";

// Use generated type for token usage
export type TokenUsage = components["schemas"]["TokenUsage"];

// Local types for nested review structure (different from flat API response)
export interface ReviewContent {
  summary: string;
  strengths: string[];
  weaknesses: string[];
  questions: string[];
  limitations: string[];
  ethical_concerns: boolean;
  ethical_concerns_explanation: string;
  originality: number;
  quality: number;
  clarity: number;
  significance: number;
  soundness: number;
  presentation: number;
  contribution: number;
  overall: number;
  confidence: number;
  decision: string;
}

export interface PaperReviewResponse {
  id: number;
  review: ReviewContent;
  token_usage: TokenUsage;
  cost_cents: number;
  original_filename: string;
  model: string;
  created_at: string;
}

interface PaperReviewResultProps {
  review: PaperReviewResponse;
}

interface ScoreMetric {
  label: string;
  key: keyof ReviewContent;
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

function getScoreLabel(key: keyof ReviewContent, score: number): string {
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

function getDecisionColor(decision: string): string {
  const d = decision.toLowerCase();
  if (d.includes("accept")) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  if (d.includes("reject")) return "text-red-400 bg-red-500/10 border-red-500/30";
  return "text-amber-400 bg-amber-500/10 border-amber-500/30";
}

function getDecisionIcon(decision: string) {
  const d = decision.toLowerCase();
  if (d.includes("accept")) return <CheckCircle className="h-5 w-5" />;
  if (d.includes("reject")) return <XCircle className="h-5 w-5" />;
  return <HelpCircle className="h-5 w-5" />;
}

function getScoreColor(score: number, max: number): string {
  const ratio = score / max;
  if (ratio >= 0.75) return "text-emerald-400";
  if (ratio >= 0.5) return "text-amber-400";
  return "text-red-400";
}

function CollapsibleSection({
  title,
  icon,
  children,
  defaultOpen = true,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="font-medium text-white">{title}</span>
        </div>
        {isOpen ? (
          <ChevronUp className="h-5 w-5 text-slate-400" />
        ) : (
          <ChevronDown className="h-5 w-5 text-slate-400" />
        )}
      </button>
      {isOpen && <div className="border-t border-slate-700 p-4">{children}</div>}
    </div>
  );
}

export function PaperReviewResult({ review }: PaperReviewResultProps) {
  const content = review.review;
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const headers = withAuthHeaders(new Headers());
      const response = await fetch(`${config.apiUrl}/paper-reviews/${review.id}/download`, {
        headers,
        credentials: "include",
      });

      if (!response.ok) {
        return;
      }

      const data = await response.json();
      // Open the download URL in a new tab (it's a signed S3 URL)
      window.open(data.download_url, "_blank");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Decision Banner */}
      <div
        className={`flex items-center justify-between rounded-lg border p-4 ${getDecisionColor(content.decision)}`}
      >
        <div className="flex items-center gap-3">
          {getDecisionIcon(content.decision)}
          <div>
            <div className="font-semibold">{content.decision}</div>
            <div className="text-sm opacity-80">Cost: ${(review.cost_cents / 100).toFixed(2)}</div>
          </div>
        </div>
        <button
          onClick={handleDownload}
          disabled={isDownloading}
          className="flex items-center gap-2 rounded-lg border border-current px-3 py-1.5 text-sm transition-opacity hover:opacity-80 disabled:opacity-50"
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

      {/* Summary */}
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h3 className="mb-3 font-medium text-white">Summary</h3>
        <p className="text-sm leading-relaxed text-slate-300">{content.summary}</p>
      </div>

      {/* Scores Grid */}
      <div>
        <h3 className="mb-3 font-medium text-white">Quantitative Scores</h3>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
          {SCORE_METRICS.map(metric => {
            const score = content[metric.key] as number;
            const label = getScoreLabel(metric.key, score);
            return (
              <div
                key={metric.label}
                className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 text-center"
              >
                <div className="mb-1 text-xs text-slate-400">{metric.label}</div>
                <div className={`text-xl font-bold ${getScoreColor(score, metric.max)}`}>
                  {score}
                  <span className="text-sm font-normal text-slate-500">/{metric.max}</span>
                </div>
                {label && <div className="mt-1 text-xs text-slate-500">{label}</div>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Strengths */}
      <CollapsibleSection
        title={`Strengths (${content.strengths.length})`}
        icon={<ThumbsUp className="h-5 w-5 text-emerald-400" />}
      >
        <ul className="space-y-2">
          {content.strengths.map((strength, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-300">
              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-400" />
              {strength}
            </li>
          ))}
        </ul>
      </CollapsibleSection>

      {/* Weaknesses */}
      <CollapsibleSection
        title={`Weaknesses (${content.weaknesses.length})`}
        icon={<ThumbsDown className="h-5 w-5 text-red-400" />}
      >
        <ul className="space-y-2">
          {content.weaknesses.map((weakness, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-300">
              <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-red-400" />
              {weakness}
            </li>
          ))}
        </ul>
      </CollapsibleSection>

      {/* Questions */}
      {content.questions.length > 0 && (
        <CollapsibleSection
          title={`Questions (${content.questions.length})`}
          icon={<HelpCircle className="h-5 w-5 text-sky-400" />}
          defaultOpen={false}
        >
          <ul className="space-y-2">
            {content.questions.map((question, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-sky-400" />
                {question}
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Limitations */}
      {content.limitations.length > 0 && (
        <CollapsibleSection
          title={`Limitations (${content.limitations.length})`}
          icon={<AlertTriangle className="h-5 w-5 text-amber-400" />}
          defaultOpen={false}
        >
          <ul className="space-y-2">
            {content.limitations.map((limitation, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400" />
                {limitation}
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Ethical Concerns */}
      {content.ethical_concerns && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-400">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <span className="text-sm font-medium">
              Ethical concerns were identified in this paper
            </span>
          </div>
          {content.ethical_concerns_explanation && (
            <p className="mt-2 text-sm text-red-300">{content.ethical_concerns_explanation}</p>
          )}
        </div>
      )}

      {/* Token Usage */}
      <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-4 text-xs text-slate-500">
        <span className="font-medium">Token usage:</span>{" "}
        {review.token_usage.input_tokens.toLocaleString()} input
        {review.token_usage.cached_input_tokens > 0 && (
          <span> ({review.token_usage.cached_input_tokens.toLocaleString()} cached)</span>
        )}
        , {review.token_usage.output_tokens.toLocaleString()} output
      </div>
    </div>
  );
}
