import type { SubstageSummary } from "@/types/research";

// =============================================================================
// STAGE CONSTANTS
// =============================================================================

export const FULL_TREE_STAGE_ID = "full_tree";

/**
 * Stage goal descriptions shown in the Tree Visualization UI
 * Note: The research pipeline uses uppercase "Stage_N" format in tree viz data
 */
export const STAGE_SUMMARIES: Record<string, string> = {
  Stage_1:
    "Goal: Develop functional code which can produce a runnable result. The tree represents attempts and fixes needed to reach this state.",
  Stage_2:
    "Goal: Improve the baseline through tuning and small changes to the code while keeping the overall approach fixed. The scientist tries to improve the metrics which quantify the quality of the research.",
  Stage_3:
    "Goal: Explore higher-leverage variants and research directions, supported by plots and analyses to understand what is driving performance. The scientist tries to find and validate meaningful improvements worth writing up.",
  Stage_4:
    "Goal: Run controlled ablations and robustness checks to isolate which components matter and why. The scientist tries to attribute gains and strengthen the evidence for the final claims.",
  [FULL_TREE_STAGE_ID]:
    "Combined view showing all stages of the research pipeline stacked vertically in chronological order.",
};

/**
 * Maps frontend stage IDs (Stage_1, etc.) to backend stage slugs (initial_implementation, etc.)
 * Note: The research pipeline uses uppercase "Stage_N" format in tree viz data
 */
export const STAGE_ID_TO_SLUG: Record<string, string> = {
  Stage_1: "initial_implementation",
  Stage_2: "baseline_tuning",
  Stage_3: "creative_research",
  Stage_4: "ablation_studies",
};

// =============================================================================
// STAGE UTILITY FUNCTIONS
// =============================================================================

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
  if (!isRecord(summary.summary)) {
    return JSON.stringify(summary.summary, null, 2);
  }
  const llmSummary = summary.summary.llm_summary;
  if (typeof llmSummary === "string" && llmSummary.trim().length > 0) {
    return llmSummary.trim();
  }
  return JSON.stringify(summary.summary, null, 2);
}

