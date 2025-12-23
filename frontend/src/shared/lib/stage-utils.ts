import type { SubstageSummary } from "@/types/research";

/**
 * Convert stage ID to human-readable label
 * Example: "Stage_1" → "Stage 1"
 */
export function stageLabel(stageId: string): string {
  return stageId.replace("Stage_", "Stage ");
}

/**
 * Type guard to check if a value is a Record object
 */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Extract stage slug from backend stage name
 *
 * Backend format: {stage_number}_{stage_slug}[_{substage_number}_{substage_slug}...]
 * Examples:
 *   "1_initial_implementation" → "initial_implementation"
 *   "2_baseline_tuning_2_optimization" → "baseline_tuning"
 *   "3_creative_research_1_exploration" → "creative_research"
 */
export function extractStageSlug(stageName: string): string | null {
  const parts = stageName.split("_");

  // Need at least 2 parts: stage_number + slug
  if (parts.length < 2) return null;

  // Skip first part (stage number), collect parts until we hit next number (substage number)
  const slugParts: string[] = [];
  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue;
    // Stop when we hit a number (substage number)
    if (/^\d+$/.test(part)) break;
    slugParts.push(part);
  }

  return slugParts.length > 0 ? slugParts.join("_") : null;
}

/**
 * Extract display text from a SubstageSummary
 * Prefers the llm_summary field if available, otherwise JSON stringifies the summary
 */
export function getSummaryText(summary: SubstageSummary): string {
  if (!isRecord(summary.summary)) {
    return JSON.stringify(summary.summary, null, 2);
  }
  const llmSummary = summary.summary.llm_summary;
  if (typeof llmSummary === "string" && llmSummary.trim().length > 0) {
    return llmSummary.trim();
  }
  return JSON.stringify(summary.summary, null, 2);
}

