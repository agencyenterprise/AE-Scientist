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

export interface ArtifactMetadataApi {
  id: number;
  artifact_type: string;
  filename: string;
  file_size: number;
  file_type: string;
  created_at: string;
  download_path: string;
}

export interface ResearchRunDetailsApi {
  run: ResearchRunInfoApi;
  stage_progress: StageProgressApi[];
  logs: LogEntryApi[];
  substage_events: SubstageEventApi[];
  artifacts: ArtifactMetadataApi[];
  tree_viz: TreeVizItemApi[];
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

export interface ArtifactMetadata {
  id: number;
  artifact_type: string;
  filename: string;
  file_size: number;
  file_type: string;
  created_at: string;
  download_path: string;
}

export interface ArtifactPresignedUrlResponse {
  url: string;
  expires_in: number;
  artifact_id: number;
  filename: string;
}

export interface ResearchRunDetails {
  run: ResearchRunInfo;
  stage_progress: StageProgress[];
  logs: LogEntry[];
  substage_events: SubstageEvent[];
  artifacts: ArtifactMetadata[];
  tree_viz: TreeVizItem[];
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
