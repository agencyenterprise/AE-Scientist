/**
 * Types for research pipeline runs
 *
 * This file re-exports generated types from the OpenAPI schema and defines
 * additional frontend-specific types for transformation and UI purposes.
 */

import type { components } from "./api.gen";

// ===========================================
// Re-export generated API types
// ===========================================

// List types
export type ResearchRunListItemApi = components["schemas"]["ResearchRunListItem"];
export type ResearchRunListResponseApi = components["schemas"]["ResearchRunListResponse"];

// Run info and details
export type ResearchRunInfoApi = components["schemas"]["ResearchRunInfo"];
export type ResearchRunDetailsApi = components["schemas"]["ResearchRunDetailsResponse"];

// Progress and events
export type StageProgressApi = components["schemas"]["ResearchRunStageProgress"];
export type StageEventApi = components["schemas"]["ResearchRunStageEvent"];
export type StageSummaryApi = components["schemas"]["ResearchRunStageSummary"];
export type PaperGenerationEventApi = components["schemas"]["ResearchRunPaperGenerationProgress"];

// Artifacts and selections
export type ArtifactMetadataApi = components["schemas"]["ResearchRunArtifactMetadata"];
export type ArtifactType = components["schemas"]["ArtifactType"];
export type StageSkipWindowApi = components["schemas"]["ResearchRunStageSkipWindow"];
export type StageSkipWindowUpdate = components["schemas"]["ResearchRunStageSkipWindowUpdate"];

// Tree visualization
export type TreeVizItemApi = components["schemas"]["TreeVizItem"];

// Code execution
export type ResearchRunCodeExecution = components["schemas"]["ResearchRunCodeExecution"];

// Cost types
export type HwCostEstimateData = components["schemas"]["ResearchRunHwCostEstimateData"];
export type HwCostActualData = components["schemas"]["ResearchRunHwCostActualData"];

// Termination status
export type TerminationStatusData = components["schemas"]["ResearchRunTerminationStatusData"];

// LLM Review
export type LlmReviewResponse = components["schemas"]["LlmReviewResponse"];

// Run tree
export type RunTreeNode = components["schemas"]["RunTreeNodeResponse"];
export type RunTreeResponse = components["schemas"]["RunTreeResponse"];

// Child conversations
export type ChildConversationInfo = components["schemas"]["ChildConversationInfo"];

// GPU types
export type ResearchGpuTypesResponse = components["schemas"]["GpuTypeListResponse"];

// Artifact URL response
export type ArtifactPresignedUrlResponse = components["schemas"]["ArtifactPresignedUrlResponse"];

// ===========================================
// Frontend types (camelCase transformations)
// ===========================================

// Frontend types for the list view
export interface ResearchRun {
  runId: string;
  status: string;
  initializationStatus: string;
  ideaTitle: string;
  ideaMarkdown: string | null; // Full idea content in markdown format
  currentStage: string | null;
  progress: number | null;
  gpuType: string;
  bestMetric: string | null;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
  artifactsCount: number;
  errorMessage: string | null;
  conversationId: number;
  parentRunId: string | null;
}

export interface ResearchRunListResponse {
  items: ResearchRun[];
  total: number;
}

// Status type for UI styling
export type ResearchRunStatus = "pending" | "initializing" | "running" | "completed" | "failed";

export type ResearchRunTerminationStatus =
  | "none"
  | "requested"
  | "in_progress"
  | "terminated"
  | "failed";

// ===========================================
// Aliases for snake_case types (SSE compatibility)
// ===========================================

// These aliases use the generated API types directly since the frontend
// uses snake_case for SSE event handling
export type ResearchRunInfo = ResearchRunInfoApi;
export type StageProgress = StageProgressApi;
export type StageEvent = StageEventApi;
export type StageSummary = StageSummaryApi;
export type PaperGenerationEvent = PaperGenerationEventApi;
export type ArtifactMetadata = ArtifactMetadataApi;
export type StageSkipWindow = StageSkipWindowApi;
export type TreeVizItem = TreeVizItemApi;

// ===========================================
// Frontend detail types
// ===========================================

export type RunType = components["schemas"]["RunType"];

export interface ResearchRunDetails {
  run: ResearchRunInfo;
  stage_progress: StageProgress[];
  stage_events: StageEvent[];
  stage_summaries: StageSummary[];
  artifacts: ArtifactMetadata[];
  paper_generation_progress: PaperGenerationEvent[];
  tree_viz: TreeVizItem[];
  stage_skip_windows?: StageSkipWindow[];
  hw_cost_estimate?: HwCostEstimateData | null;
  hw_cost_actual?: HwCostActualData | null;
  code_executions: Partial<Record<RunType, ResearchRunCodeExecution>>;
  child_conversations?: ChildConversationInfo[];
}

// ===========================================
// SSE Event types
// ===========================================

export type TerminationStatusStreamEvent =
  components["schemas"]["ResearchRunTerminationStatusEvent"];

export type HwCostEstimateEvent = components["schemas"]["ResearchRunHwCostEstimateEvent"];

export type HwCostActualEvent = components["schemas"]["ResearchRunHwCostActualEvent"];

// ===========================================
// Node summary types
// ===========================================

export interface NodeSummary {
  findings: string;
  significance: string;
  next_steps?: string | null;
  is_buggy: boolean;
  metric?: string | null;
}

// ===========================================
// Tree visualization types
// ===========================================

export interface StageZone {
  min: number;
  max: number;
}

export interface StageZoneMetadata {
  stageIndex: number;
  stageId: string;
  zone: StageZone;
}

export interface MergedTreeVizPayload {
  layout: Array<[number, number]>;
  edges: Array<[number, number]>;
  stageIds: string[];
  originalNodeIds: number[];
  zoneMetadata?: StageZoneMetadata[];
  code?: string[];
  codex_task?: string[];
  plan?: string[];
  analysis?: string[];
  metrics?: Array<unknown>;
  exc_type?: Array<string | null>;
  exc_info?: Array<{ args?: unknown[] } | null>;
  exc_stack?: Array<unknown>;
  plot_plan?: Array<string | null>;
  plot_code?: Array<string | null>;
  plot_analyses?: Array<unknown>;
  plots?: Array<string | string[] | null>;
  plot_paths?: Array<string | string[] | null>;
  vlm_feedback_summary?: Array<string | string[] | null>;
  datasets_successfully_tested?: Array<string[] | null>;
  exec_time?: Array<number | string | null>;
  exec_time_feedback?: Array<string | null>;
  is_best_node?: Array<boolean>;
  is_seed_node?: Array<boolean>;
  is_seed_agg_node?: Array<boolean>;
  ablation_name?: Array<string | null>;
  hyperparam_name?: Array<string | null>;
}

export interface MergedTreeViz extends Omit<TreeVizItem, "stage_id" | "viz"> {
  stage_id: "full_tree";
  viz: MergedTreeVizPayload;
}

// ===========================================
// LLM Review helper types
// ===========================================

export interface LlmReviewNotFoundResponse {
  run_id: string;
  exists: false;
  message: string;
}

/**
 * Type guard to discriminate between LlmReviewResponse and LlmReviewNotFoundResponse
 */
export function isReview(
  response: LlmReviewResponse | LlmReviewNotFoundResponse
): response is LlmReviewResponse {
  return "exists" in response ? response.exists !== false : true;
}
