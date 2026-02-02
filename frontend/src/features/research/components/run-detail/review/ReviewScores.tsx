"use client";

import type { LlmReviewResponse } from "@/types/research";

interface ReviewScoresProps {
  review: LlmReviewResponse;
}

interface ScoreMetric {
  label: string;
  key: keyof LlmReviewResponse;
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

function getScoreLabel(key: keyof LlmReviewResponse, score: number): string {
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

/**
 * ReviewScores Component
 *
 * Displays quantitative evaluation scores in a responsive grid.
 * Shows 9 metrics with their scores and semantic labels.
 *
 * Grid layout:
 * - 2 columns on mobile
 * - 3 columns on tablet and up
 *
 * Each metric card shows:
 * - Metric name (uppercase, muted foreground)
 * - Score value (large, bold)
 * - Semantic label (e.g., "High", "Good", "Accept")
 *
 * @param review - The LlmReviewResponse object containing score data
 */
export function ReviewScores({ review }: ReviewScoresProps) {
  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">📊 Quantitative Scores</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {SCORE_METRICS.map(metric => {
          const score = review[metric.key] as number;
          const label = getScoreLabel(metric.key, score);
          return (
            <div key={metric.label} className="bg-muted rounded-lg p-4">
              <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                {metric.label}
              </div>
              <div className="text-2xl font-bold text-yellow-300">
                {score}
                <span className="text-sm text-muted-foreground font-normal">/{metric.max}</span>
              </div>
              {label && <div className="text-xs text-muted-foreground mt-1">{label}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
