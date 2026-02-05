import type { SubstageSummary } from "@/types/research";

// =============================================================================
// STAGE CONSTANTS
// =============================================================================

export const FULL_TREE_STAGE_ID = "full_tree";

/**
 * Stage goal descriptions shown in the Tree Visualization UI
 */
export const STAGE_SUMMARIES: Record<string, string> = {
  stage_1:
    "Goal: Develop functional code which can produce a runnable result. The tree represents attempts and fixes needed to reach this state.",
  stage_2:
    "Goal: Improve the baseline through tuning and small changes to the code while keeping the overall approach fixed. The scientist tries to improve the metrics which quantify the quality of the research.",
  stage_3:
    "Goal: Explore higher-leverage variants and research directions, supported by plots and analyses to understand what is driving performance. The scientist tries to find and validate meaningful improvements worth writing up.",
  stage_4:
    "Goal: Run controlled ablations and robustness checks to isolate which components matter and why. The scientist tries to attribute gains and strengthen the evidence for the final claims.",
  [FULL_TREE_STAGE_ID]:
    "Combined view showing all stages of the research pipeline stacked vertically in chronological order.",
};

/**
 * Maps frontend stage IDs (stage_1, etc.) to backend stage slugs (initial_implementation, etc.)
 */
export const STAGE_ID_TO_SLUG: Record<string, string> = {
  stage_1: "initial_implementation",
  stage_2: "baseline_tuning",
  stage_3: "creative_research",
  stage_4: "ablation_studies",
  stage_5: "paper_generation",
};

// =============================================================================
// STAGE UTILITY FUNCTIONS
// =============================================================================

/**
 * Normalize stage ID to lowercase format (stage_N)
 * Handles both "Stage_N" and "stage_N" formats from different data sources
 */
export function normalizeStageId(stageId: string): string {
  // Match "Stage_N" or "stage_N" and normalize to lowercase
  const match = stageId.match(/^[Ss]tage_(\d+)$/);
  if (match && match[1]) {
    return `stage_${match[1]}`;
  }
  return stageId;
}

/**
 * Get stage summary for a stage ID (case-insensitive lookup)
 */
export function getStageSummary(stageId: string): string | undefined {
  return STAGE_SUMMARIES[normalizeStageId(stageId)];
}

/**
 * Get stage slug for a stage ID (case-insensitive lookup)
 */
export function getStageSlug(stageId: string): string | undefined {
  return STAGE_ID_TO_SLUG[normalizeStageId(stageId)];
}

/**
 * Human-readable stage labels by stage number
 */
const STAGE_LABELS: Record<string, string> = {
  "1": "Stage 1",
  "2": "Stage 2",
  "3": "Stage 3",
  "4": "Stage 4",
  "5": "Stage 5",
};

/**
 * Convert stage ID to human-readable label
 */
export function stageLabel(stageId: string): string {
  // Extract the number from "stage_N" or "Stage_N" format
  const match = stageId.match(/^[Ss]tage_(\d+)$/);
  if (match && match[1]) {
    return STAGE_LABELS[match[1]] ?? `Stage ${match[1]}`;
  }

  // Fallback: just replace underscore with space
  return stageId.replace(/_/g, " ");
}

/**
 * Extract the leading stage number from a backend stage name
 *
 * Backend format: {stage_number}_{stage_slug}[_{substage_number}_{substage_slug}...]
 * Examples:
 *   "1_initial_implementation" → "1"
 *   "5_paper_generation" → "5"
 */
export function extractStageNumber(stageName: string): string | null {
  const match = stageName.match(/^(\d+)(?:_|$)/);
  return match?.[1] ?? null;
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
  // Type assertion needed because backend returns dict which maps to Record<string, never>
  const summaryData = summary.summary as Record<string, unknown>;
  if (!isRecord(summaryData)) {
    return JSON.stringify(summaryData, null, 2);
  }
  const llmSummary = summaryData.llm_summary;
  if (typeof llmSummary === "string" && llmSummary.trim().length > 0) {
    return llmSummary.trim();
  }
  return JSON.stringify(summaryData, null, 2);
}
