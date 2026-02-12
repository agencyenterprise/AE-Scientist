import type { LlmReviewResponse } from "@/types/research";

/**
 * Generates markdown content from the review data
 */
export function generateEvaluationMarkdown(review: LlmReviewResponse): string {
  const verdict = review.decision === "Accept" ? "PASS" : "FAIL";
  const lines: string[] = [];

  lines.push(`# Evaluation Details`);
  lines.push("");
  lines.push(`**Verdict:** ${verdict}`);
  lines.push(`**Decision:** ${review.decision}`);
  lines.push(`**Date:** ${new Date(review.created_at).toLocaleDateString()}`);
  lines.push("");

  // Scores section
  lines.push(`## Scores`);
  lines.push("");
  lines.push(`| Metric | Score |`);
  lines.push(`|--------|-------|`);
  lines.push(`| Originality | ${review.originality}/4 |`);
  lines.push(`| Quality | ${review.quality}/4 |`);
  lines.push(`| Clarity | ${review.clarity}/4 |`);
  lines.push(`| Significance | ${review.significance}/4 |`);
  lines.push(`| Soundness | ${review.soundness}/4 |`);
  lines.push(`| Presentation | ${review.presentation}/4 |`);
  lines.push(`| Contribution | ${review.contribution}/4 |`);
  lines.push(`| **Overall** | **${review.overall}/10** |`);
  lines.push(`| Confidence | ${review.confidence}/5 |`);
  lines.push("");

  // Analysis section
  lines.push(`## Analysis`);
  lines.push("");

  lines.push(`### Summary`);
  lines.push("");
  lines.push(review.summary);
  lines.push("");

  if (review.strengths.length > 0) {
    lines.push(`### Strengths`);
    lines.push("");
    review.strengths.forEach(s => lines.push(`- ${s}`));
    lines.push("");
  }

  if (review.weaknesses.length > 0) {
    lines.push(`### Weaknesses`);
    lines.push("");
    review.weaknesses.forEach(w => lines.push(`- ${w}`));
    lines.push("");
  }

  if (review.questions.length > 0) {
    lines.push(`### Questions`);
    lines.push("");
    review.questions.forEach(q => lines.push(`- ${q}`));
    lines.push("");
  }

  if (review.limitations.length > 0) {
    lines.push(`### Limitations`);
    lines.push("");
    review.limitations.forEach(l => lines.push(`- ${l}`));
    lines.push("");
  }

  if (review.ethical_concerns) {
    lines.push(`### Ethical Concerns`);
    lines.push("");
    lines.push(`This work has been flagged for potential ethical concerns.`);
    lines.push("");
  }

  return lines.join("\n");
}

/**
 * Downloads the review as a markdown file
 */
export function downloadEvaluationMarkdown(review: LlmReviewResponse): void {
  const markdown = generateEvaluationMarkdown(review);
  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `evaluation-${review.run_id}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
