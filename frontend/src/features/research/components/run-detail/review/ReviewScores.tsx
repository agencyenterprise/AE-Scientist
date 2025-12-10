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

/**
 * ReviewScores Component
 *
 * Displays quantitative evaluation scores in a responsive grid.
 * Shows 9 metrics with their scores displayed as fractions (e.g., 3/4, 8/10).
 *
 * Grid layout:
 * - 2 columns on mobile
 * - 3 columns on tablet and up
 *
 * Each metric card shows:
 * - Metric name (uppercase, muted foreground)
 * - Score value (large, bold) with max value (smaller, muted)
 *
 * @param review - The LlmReviewResponse object containing score data
 */
export function ReviewScores({ review }: ReviewScoresProps) {
  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">📊 Quantitative Scores</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {SCORE_METRICS.map(metric => {
          const score = review[metric.key];
          return (
            <div key={metric.label} className="bg-muted rounded-lg p-4">
              <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                {metric.label}
              </div>
              <div className="text-2xl font-bold text-yellow-300">
                {score}{" "}
                <span className="text-sm text-muted-foreground font-normal">/ {metric.max}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
