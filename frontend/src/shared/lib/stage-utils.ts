// =============================================================================
// STAGE CONSTANTS - Using canonical stage IDs from generated API types
// =============================================================================

import type { StageId } from "@/types";

// Re-export the generated type for convenience
export type { StageId };

export const FULL_TREE_STAGE_ID = "full_tree";

/**
 * Canonical stage IDs used throughout the system.
 * Values must match the generated StageId enum from the API schema.
 */
export const STAGE_ID = {
  INITIAL_IMPLEMENTATION: "1_initial_implementation",
  BASELINE_TUNING: "2_baseline_tuning",
  CREATIVE_RESEARCH: "3_creative_research",
  ABLATION_STUDIES: "4_ablation_studies",
  PAPER_GENERATION: "5_paper_generation",
} as const satisfies Record<string, StageId>;

/**
 * Stage goal descriptions shown in the Tree Visualization UI
 */
export const STAGE_SUMMARIES: Record<string, string> = {
  [STAGE_ID.INITIAL_IMPLEMENTATION]:
    "Goal: Develop functional code which can produce a runnable result. The tree represents attempts and fixes needed to reach this state.",
  [STAGE_ID.BASELINE_TUNING]:
    "Goal: Improve the baseline through tuning and small changes to the code while keeping the overall approach fixed. The scientist tries to improve the metrics which quantify the quality of the research.",
  [STAGE_ID.CREATIVE_RESEARCH]:
    "Goal: Explore higher-leverage variants and research directions, supported by plots and analyses to understand what is driving performance. The scientist tries to find and validate meaningful improvements worth writing up.",
  [STAGE_ID.ABLATION_STUDIES]:
    "Goal: Run controlled ablations and robustness checks to isolate which components matter and why. The scientist tries to attribute gains and strengthen the evidence for the final claims.",
  [FULL_TREE_STAGE_ID]:
    "Combined view showing all stages of the research pipeline stacked vertically in chronological order.",
};

/**
 * Stage metadata: ID to number, title, and description
 */
export const STAGE_METADATA: Record<
  StageId,
  { number: string; title: string; description: string }
> = {
  [STAGE_ID.INITIAL_IMPLEMENTATION]: {
    number: "1",
    title: "Baseline Implementation",
    description: "Generate working baseline implementation with basic functional correctness",
  },
  [STAGE_ID.BASELINE_TUNING]: {
    number: "2",
    title: "Baseline Tuning",
    description: "Hyperparameter optimization to improve baseline performance",
  },
  [STAGE_ID.CREATIVE_RESEARCH]: {
    number: "3",
    title: "Creative Research",
    description: "Novel improvements, plotting, and visualization generation",
  },
  [STAGE_ID.ABLATION_STUDIES]: {
    number: "4",
    title: "Ablation Studies",
    description: "Component analysis to validate individual contributions",
  },
  [STAGE_ID.PAPER_GENERATION]: {
    number: "5",
    title: "Paper Generation",
    description: "Plot aggregation, citation gathering, paper writeup, and peer review",
  },
};

/**
 * All stage IDs in order
 */
export const STAGE_IDS = [
  STAGE_ID.INITIAL_IMPLEMENTATION,
  STAGE_ID.BASELINE_TUNING,
  STAGE_ID.CREATIVE_RESEARCH,
  STAGE_ID.ABLATION_STUDIES,
  STAGE_ID.PAPER_GENERATION,
] as const;

/**
 * Stages 1-4 are skippable (paper_generation is NOT skippable)
 */
export const SKIPPABLE_STAGES = [
  STAGE_ID.INITIAL_IMPLEMENTATION,
  STAGE_ID.BASELINE_TUNING,
  STAGE_ID.CREATIVE_RESEARCH,
  STAGE_ID.ABLATION_STUDIES,
] as const;

/**
 * Pipeline stage metadata for UI components
 */
export const PIPELINE_STAGES = [
  {
    id: 1,
    key: STAGE_ID.INITIAL_IMPLEMENTATION,
    ...STAGE_METADATA[STAGE_ID.INITIAL_IMPLEMENTATION],
  },
  { id: 2, key: STAGE_ID.BASELINE_TUNING, ...STAGE_METADATA[STAGE_ID.BASELINE_TUNING] },
  { id: 3, key: STAGE_ID.CREATIVE_RESEARCH, ...STAGE_METADATA[STAGE_ID.CREATIVE_RESEARCH] },
  { id: 4, key: STAGE_ID.ABLATION_STUDIES, ...STAGE_METADATA[STAGE_ID.ABLATION_STUDIES] },
  { id: 5, key: STAGE_ID.PAPER_GENERATION, ...STAGE_METADATA[STAGE_ID.PAPER_GENERATION] },
] as const;

// =============================================================================
// STAGE UTILITY FUNCTIONS
// =============================================================================

/**
 * Normalize stage ID for tree visualization lookup
 * Maps "1_initial_implementation" to "stage_1" for legacy compatibility
 */
export function normalizeStageId(stageId: string): string {
  const meta = STAGE_METADATA[stageId as StageId];
  if (meta) {
    return `stage_${meta.number}`;
  }
  // Fallback for legacy "stage_N" or "Stage_N" formats
  const match = stageId.match(/^[Ss]tage_(\d+)$/);
  if (match && match[1]) {
    return `stage_${match[1]}`;
  }
  return stageId;
}

/**
 * Get stage summary for a stage ID
 */
export function getStageSummary(stageId: string): string | undefined {
  return STAGE_SUMMARIES[stageId] ?? STAGE_SUMMARIES[normalizeStageId(stageId)];
}

/**
 * Convert stage ID to human-readable label (e.g., "Stage 1", "Stage 2")
 */
export function stageLabel(stageId: string): string {
  const meta = STAGE_METADATA[stageId as StageId];
  if (meta) {
    return `Stage ${meta.number}`;
  }
  // Fallback: just replace underscore with space
  return stageId.replace(/_/g, " ");
}

/**
 * Convert stage ID to descriptive stage name (e.g., "Baseline Tuning", "Creative Research")
 */
export function stageName(stageId: string): string {
  const meta = STAGE_METADATA[stageId as StageId];
  if (meta) {
    return meta.title;
  }
  // Fallback: just replace underscore with space
  return stageId.replace(/_/g, " ");
}

/**
 * Get stage number from a stage ID
 */
export function extractStageNumber(stageId: string): string | null {
  const meta = STAGE_METADATA[stageId as StageId];
  return meta?.number ?? null;
}

/**
 * Type guard to check if a value is a Record object
 */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
