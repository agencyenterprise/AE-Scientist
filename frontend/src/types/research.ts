/**
 * Types for research pipeline runs
 */

// API Response types (snake_case from backend)
export interface ResearchRunListItemApi {
  run_id: string;
  status: string;
  idea_title: string;
  idea_hypothesis: string | null;
  current_stage: string | null;
  progress: number | null;
  gpu_type: string | null;
  best_metric: string | null;
  created_by_name: string;
  created_at: string;
  updated_at: string;
  artifacts_count: number;
  error_message: string | null;
  conversation_id: number;
}

export interface ResearchRunListResponseApi {
  items: ResearchRunListItemApi[];
  total: number;
}

// Frontend types (camelCase)
export interface ResearchRun {
  runId: string;
  status: string;
  ideaTitle: string;
  ideaHypothesis: string | null;
  currentStage: string | null;
  progress: number | null;
  gpuType: string | null;
  bestMetric: string | null;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
  artifactsCount: number;
  errorMessage: string | null;
  conversationId: number;
}

export interface ResearchRunListResponse {
  items: ResearchRun[];
  total: number;
}

export interface ResearchGpuTypesResponse {
  gpu_types: string[];
}

// Status type for UI styling
export type ResearchRunStatus = "pending" | "running" | "completed" | "failed";

// ==========================================
// Research Run Detail Types (for [runId] page)
// ==========================================

// API Response types (snake_case from backend)
export interface ResearchRunInfoApi {
  run_id: string;
  status: string;
  idea_id: number;
  idea_version_id: number;
  pod_id: string | null;
  pod_name: string | null;
  gpu_type: string | null;
  public_ip: string | null;
  ssh_port: string | null;
  pod_host_id: string | null;
  error_message: string | null;
  last_heartbeat_at: string | null;
  heartbeat_failures: number;
  created_at: string;
  updated_at: string;
  start_deadline_at: string | null;
}

export interface StageProgressApi {
  stage: string;
  iteration: number;
  max_iterations: number;
  progress: number;
  total_nodes: number;
  buggy_nodes: number;
  good_nodes: number;
  best_metric: string | null;
  eta_s: number | null;
  latest_iteration_time_s: number | null;
  created_at: string;
}

export interface LogEntryApi {
  id: number;
  level: string;
  message: string;
  created_at: string;
}

export interface NodeSummary {
  findings: string;
  significance: string;
  next_steps?: string | null;
  is_buggy: boolean;
  metric?: string | null;
}

export interface SubstageEventApi {
  id: number;
  stage: string;
  summary: NodeSummary | Record<string, unknown>; // Summary payload stored for this sub-stage
  created_at: string;
}

export interface SubstageSummaryApi {
  id: number;
  stage: string;
  summary: Record<string, unknown>;
  created_at: string;
}

export interface PaperGenerationEventApi {
  id: number;
  run_id: string;
  step: string;
  substep: string | null;
  progress: number;
  step_progress: number;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface ArtifactMetadataApi {
  id: number;
  artifact_type: string;
  filename: string;
  file_size: number;
  file_type: string;
  created_at: string;
}

export interface BestNodeSelectionApi {
  id: number;
  stage: string;
  node_id: string;
  reasoning: string;
  created_at: string;
}

export interface StageSkipWindowApi {
  id: number;
  stage: string;
  opened_at: string;
  opened_reason: string | null;
  closed_at: string | null;
  closed_reason: string | null;
}

export interface ResearchRunDetailsApi {
  run: ResearchRunInfoApi;
  stage_progress: StageProgressApi[];
  logs: LogEntryApi[];
  substage_events: SubstageEventApi[];
  substage_summaries?: SubstageSummaryApi[];
  artifacts: ArtifactMetadataApi[];
  paper_generation_progress: PaperGenerationEventApi[];
  tree_viz: TreeVizItemApi[];
  best_node_selections?: BestNodeSelectionApi[];
  stage_skip_windows?: StageSkipWindowApi[];
  code_execution?: ResearchRunCodeExecution | null;
}

// Frontend types (camelCase) - using same structure for SSE compatibility
export interface ResearchRunInfo {
  run_id: string;
  status: string;
  idea_id: number;
  idea_version_id: number;
  pod_id: string | null;
  pod_name: string | null;
  gpu_type: string | null;
  public_ip: string | null;
  ssh_port: string | null;
  pod_host_id: string | null;
  error_message: string | null;
  last_heartbeat_at: string | null;
  heartbeat_failures: number;
  created_at: string;
  updated_at: string;
  start_deadline_at: string | null;
}

export interface HwCostEstimateData {
  hw_estimated_cost_cents: number;
  hw_cost_per_hour_cents: number;
  hw_started_running_at: string;
}

export interface HwCostEstimateEvent {
  type: "hw_cost_estimate";
  data: HwCostEstimateData;
}

export interface HwCostActualData {
  hw_actual_cost_cents: number;
  hw_actual_cost_updated_at: string;
  billing_summary: Record<string, unknown>;
}

export interface HwCostActualEvent {
  type: "hw_cost_actual";
  data: HwCostActualData;
}

export interface StageProgress {
  stage: string;
  iteration: number;
  max_iterations: number;
  progress: number;
  total_nodes: number;
  buggy_nodes: number;
  good_nodes: number;
  best_metric: string | null;
  eta_s: number | null;
  latest_iteration_time_s: number | null;
  created_at: string;
}

export interface LogEntry {
  id: number;
  level: string;
  message: string;
  created_at: string;
}

export interface SubstageEvent {
  id: number;
  stage: string;
  summary: NodeSummary | Record<string, unknown>; // Summary payload stored for this sub-stage
  created_at: string;
}

export interface SubstageSummary {
  id: number;
  stage: string;
  summary: Record<string, unknown>;
  created_at: string;
}

export interface PaperGenerationEvent {
  id: number;
  run_id: string;
  step: string;
  substep: string | null;
  progress: number;
  step_progress: number;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface ResearchRunCodeExecution {
  execution_id: string;
  stage_name: string;
  run_type: string;
  code: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
  exec_time?: number | null;
}

export interface ArtifactMetadata {
  id: number;
  artifact_type: string;
  filename: string;
  file_size: number;
  file_type: string;
  created_at: string;
}

export interface ArtifactPresignedUrlResponse {
  url: string;
  expires_in: number;
  artifact_id: number;
  filename: string;
}

export interface BestNodeSelection {
  id: number;
  stage: string;
  node_id: string;
  reasoning: string;
  created_at: string;
}

export interface StageSkipWindow {
  id: number;
  stage: string;
  opened_at: string;
  opened_reason: string | null;
  closed_at: string | null;
  closed_reason: string | null;
}

export interface StageSkipWindowUpdate {
  stage: string;
  state: "opened" | "closed";
  timestamp: string;
  reason?: string | null;
}

export interface ResearchRunDetails {
  run: ResearchRunInfo;
  stage_progress: StageProgress[];
  logs: LogEntry[];
  substage_events: SubstageEvent[];
  substage_summaries: SubstageSummary[];
  artifacts: ArtifactMetadata[];
  paper_generation_progress: PaperGenerationEvent[];
  tree_viz: TreeVizItem[];
  best_node_selections?: BestNodeSelection[];
  stage_skip_windows?: StageSkipWindow[];
  hw_cost_estimate?: HwCostEstimateData | null;
  hw_cost_actual?: HwCostActualData | null;
  code_execution?: ResearchRunCodeExecution | null;
}

export interface TreeVizItemApi {
  id: number;
  run_id: string;
  stage_id: string;
  version: number;
  viz: unknown;
  created_at: string;
  updated_at: string;
}

export interface TreeVizItem {
  id: number;
  run_id: string;
  stage_id: string;
  version: number;
  viz: unknown;
  created_at: string;
  updated_at: string;
}

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

// ==========================================
// LLM Review Types (for auto-evaluation)
// ==========================================

export interface LlmReviewResponse {
  id: number;
  run_id: string;
  summary: string;
  strengths: string[];
  weaknesses: string[];
  originality: number;
  quality: number;
  clarity: number;
  significance: number;
  soundness: number;
  presentation: number;
  contribution: number;
  overall: number;
  confidence: number;
  decision: "Accept" | "Reject";
  questions: string[];
  limitations: string[];
  ethical_concerns: boolean;
  source_path: string | null;
  created_at: string;
}

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
