import { useEffect, useRef, useCallback } from "react";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import type { ResearchRunStreamEvent, ApiComponents } from "@/types";
import type {
  ResearchRunInfo,
  StageProgress,
  LogEntry,
  ArtifactMetadata,
  ResearchRunDetails,
  PaperGenerationEvent,
  BestNodeSelection,
  SubstageSummary,
  SubstageEvent,
  HwCostEstimateData,
  HwCostActualData,
  ResearchRunCodeExecution,
  StageSkipWindow,
  StageSkipWindowUpdate,
  LlmReviewResponse,
} from "@/types/research";

export type { ResearchRunDetails };

interface UseResearchRunSSEOptions {
  runId: string;
  conversationId: number | null;
  enabled: boolean;
  onInitialData: (data: ResearchRunDetails) => void;
  onStageProgress: (event: StageProgress) => void;
  onLog: (event: LogEntry) => void;
  onArtifact: (event: ArtifactMetadata) => void;
  onRunUpdate: (run: ResearchRunInfo) => void;
  onPaperGenerationProgress: (event: PaperGenerationEvent) => void;
  onComplete: (status: string) => void;
  onRunEvent?: (event: unknown) => void;
  onBestNodeSelection?: (event: BestNodeSelection) => void;
  onSubstageSummary?: (event: SubstageSummary) => void;
  onSubstageCompleted?: (event: SubstageEvent) => void;
  onError?: (error: string) => void;
  onHwCostEstimate?: (event: HwCostEstimateData) => void;
  onHwCostActual?: (event: HwCostActualData) => void;
  onCodeExecutionStarted?: (execution: ResearchRunCodeExecution) => void;
  onCodeExecutionCompleted?: (event: CodeExecutionCompletionEvent) => void;
  onStageSkipWindow?: (event: StageSkipWindowUpdate) => void;
  onReviewCompleted?: (review: LlmReviewResponse) => void;
}

interface UseResearchRunSSEReturn {
  disconnect: () => void;
}

interface CodeExecutionCompletionEvent {
  execution_id: string;
  run_type: ResearchRunCodeExecution["run_type"];
  status: "success" | "failed";
  exec_time: number;
  completed_at: string;
}

type InitialEventData = Extract<ResearchRunStreamEvent, { type: "initial" }>["data"];
type InitialRunInfo = InitialEventData["run"];
type InitialStageProgress = InitialEventData["stage_progress"][number];
type InitialPaperGenerationEvent = InitialEventData["paper_generation_progress"][number];
type ApiCodeExecutionSnapshot = ApiComponents["schemas"]["ResearchRunCodeExecution"];
type ApiCodeExecutionStartedData = ApiComponents["schemas"]["ResearchRunCodeExecutionStartedData"];
type ApiCodeExecutionCompletedData =
  ApiComponents["schemas"]["ResearchRunCodeExecutionCompletedData"];
type ApiStageSkipWindow = ApiComponents["schemas"]["ResearchRunStageSkipWindow"];

function normalizeRunInfo(run: InitialRunInfo): ResearchRunInfo {
  return {
    run_id: run.run_id,
    status: run.status,
    idea_id: run.idea_id,
    idea_version_id: run.idea_version_id,
    pod_id: run.pod_id ?? null,
    pod_name: run.pod_name ?? null,
    gpu_type: run.gpu_type ?? null,
    public_ip: run.public_ip ?? null,
    ssh_port: run.ssh_port ?? null,
    pod_host_id: run.pod_host_id ?? null,
    error_message: run.error_message ?? null,
    last_heartbeat_at: run.last_heartbeat_at ?? null,
    heartbeat_failures: run.heartbeat_failures,
    created_at: run.created_at,
    updated_at: run.updated_at,
    start_deadline_at: run.start_deadline_at ?? null,
  };
}

function normalizeStageProgress(progress: InitialStageProgress): StageProgress {
  return {
    stage: progress.stage,
    iteration: progress.iteration,
    max_iterations: progress.max_iterations,
    progress: progress.progress,
    total_nodes: progress.total_nodes,
    buggy_nodes: progress.buggy_nodes,
    good_nodes: progress.good_nodes,
    best_metric: progress.best_metric ?? null,
    eta_s: progress.eta_s ?? null,
    latest_iteration_time_s: progress.latest_iteration_time_s ?? null,
    created_at: progress.created_at,
  };
}

function normalizePaperGenerationEvent(event: InitialPaperGenerationEvent): PaperGenerationEvent {
  return {
    id: event.id,
    run_id: event.run_id,
    step: event.step,
    substep: event.substep ?? null,
    progress: event.progress,
    step_progress: event.step_progress,
    details: event.details ?? null,
    created_at: event.created_at,
  };
}

function normalizeCodeExecution(
  snapshot?: ApiCodeExecutionSnapshot | null
): ResearchRunCodeExecution | null {
  if (!snapshot) {
    return null;
  }
  return {
    execution_id: snapshot.execution_id,
    stage_name: snapshot.stage_name,
    run_type: snapshot.run_type as ResearchRunCodeExecution["run_type"],
    code: snapshot.code,
    status: snapshot.status,
    started_at: snapshot.started_at,
    completed_at: snapshot.completed_at ?? null,
    exec_time: snapshot.exec_time ?? null,
  };
}

function mapCodeExecutionStartedEvent(
  event: ApiCodeExecutionStartedData
): ResearchRunCodeExecution {
  return {
    execution_id: event.execution_id,
    stage_name: event.stage_name,
    run_type: (event.run_type ?? "codex_execution") as ResearchRunCodeExecution["run_type"],
    code: event.code,
    status: "running",
    started_at: event.started_at,
    completed_at: null,
    exec_time: null,
  };
}

function normalizeStageSkipWindow(window: ApiStageSkipWindow): StageSkipWindow {
  return {
    id: window.id,
    stage: window.stage,
    opened_at: window.opened_at,
    opened_reason: window.opened_reason ?? null,
    closed_at: window.closed_at ?? null,
    closed_reason: window.closed_reason ?? null,
  };
}

function getInitialSubstageSummaries(data: InitialEventData): SubstageSummary[] {
  if (
    typeof data === "object" &&
    data !== null &&
    "substage_summaries" in data &&
    Array.isArray((data as { substage_summaries?: unknown }).substage_summaries)
  ) {
    return (data as { substage_summaries?: SubstageSummary[] }).substage_summaries ?? [];
  }
  return [];
}

function mapInitialEventToDetails(data: InitialEventData): ResearchRunDetails {
  const initialHwCost: HwCostEstimateData | null =
    "hw_cost_estimate" in data && data.hw_cost_estimate
      ? (data.hw_cost_estimate as HwCostEstimateData)
      : null;
  const initialHwCostActual: HwCostActualData | null =
    "hw_cost_actual" in data && data.hw_cost_actual
      ? (data.hw_cost_actual as HwCostActualData)
      : null;
  const rawStageSkipWindows =
    "stage_skip_windows" in data
      ? ((data as { stage_skip_windows?: ApiStageSkipWindow[] }).stage_skip_windows ?? [])
      : [];

  return {
    run: normalizeRunInfo(data.run),
    stage_progress: data.stage_progress.map(normalizeStageProgress),
    logs: data.logs,
    substage_events: data.substage_events,
    substage_summaries: getInitialSubstageSummaries(data),
    artifacts: data.artifacts,
    paper_generation_progress: data.paper_generation_progress.map(normalizePaperGenerationEvent),
    tree_viz: data.tree_viz,
    best_node_selections: data.best_node_selections ?? [],
    stage_skip_windows: rawStageSkipWindows.map(normalizeStageSkipWindow),
    hw_cost_estimate: initialHwCost,
    hw_cost_actual: initialHwCostActual,
    code_execution: normalizeCodeExecution(
      "code_execution" in data ? (data.code_execution as ApiCodeExecutionSnapshot | null) : null
    ),
    code_executions:
      "code_execution" in data && data.code_execution
        ? (() => {
            const normalized = normalizeCodeExecution(
              data.code_execution as ApiCodeExecutionSnapshot | null
            );
            if (!normalized) {
              return null;
            }
            return {
              [normalized.run_type]: normalized,
            } as ResearchRunDetails["code_executions"];
          })()
        : null,
  };
}

export function useResearchRunSSE({
  runId,
  conversationId,
  enabled,
  onInitialData,
  onStageProgress,
  onLog,
  onArtifact,
  onRunUpdate,
  onPaperGenerationProgress,
  onComplete,
  onRunEvent,
  onHwCostEstimate,
  onHwCostActual,
  onBestNodeSelection,
  onSubstageSummary,
  onSubstageCompleted,
  onError,
  onCodeExecutionStarted,
  onCodeExecutionCompleted,
  onStageSkipWindow,
  onReviewCompleted,
}: UseResearchRunSSEOptions): UseResearchRunSSEReturn {
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const initialSnapshotFetchedRef = useRef(false);
  const maxReconnectAttempts = 5;

  const ensureInitialSnapshot = useCallback(async () => {
    if (!enabled || !conversationId || initialSnapshotFetchedRef.current) {
      return;
    }

    const snapshotResponse = await fetch(
      `${config.apiUrl}/conversations/${conversationId}/idea/research-run/${runId}/snapshot`,
      {
        headers: withAuthHeaders(new Headers({ Accept: "application/json" })),
      }
    );

    if (!snapshotResponse.ok) {
      if (snapshotResponse.status === 401) {
        window.location.href = "/login";
        return;
      }
      throw new Error(`Snapshot HTTP ${snapshotResponse.status}`);
    }

    const snapshotData = (await snapshotResponse.json()) as InitialEventData;
    const details = mapInitialEventToDetails(snapshotData);
    onInitialData(details);
    onRunUpdate(details.run);
    initialSnapshotFetchedRef.current = true;
  }, [conversationId, runId, enabled, onInitialData, onRunUpdate]);

  const connect = useCallback(async () => {
    if (!enabled || !conversationId) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await ensureInitialSnapshot();
      if (!initialSnapshotFetchedRef.current) {
        // ensureInitialSnapshot might early-return after redirect
        return;
      }

      const response = await fetch(
        `${config.apiUrl}/conversations/${conversationId}/idea/research-run/${runId}/events`,
        {
          headers: withAuthHeaders(new Headers({ Accept: "text/event-stream" })),
          signal: controller.signal,
        }
      );

      if (!response.ok) {
        if (response.status === 401) {
          window.location.href = "/login";
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body");
      }

      reconnectAttemptsRef.current = 0;
      // eslint-disable-next-line no-console
      console.debug("[Research Run SSE] Connection established");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;

          try {
            const event = JSON.parse(line.slice(6)) as ResearchRunStreamEvent;

            switch (event.type) {
              case "stage_progress":
                onStageProgress(event.data as StageProgress);
                break;
              case "run_event":
                onRunEvent?.(event.data);
                break;
              case "log":
                onLog(event.data as LogEntry);
                break;
              case "artifact":
                onArtifact(event.data as ArtifactMetadata);
                break;
              case "review_completed":
                onReviewCompleted?.(event.data as LlmReviewResponse);
                break;
              case "best_node_selection":
                onBestNodeSelection?.(event.data as BestNodeSelection);
                break;
              case "substage_summary":
                onSubstageSummary?.(event.data as SubstageSummary);
                break;
              case "substage_completed":
                onSubstageCompleted?.(event.data as SubstageEvent);
                break;
              case "paper_generation_progress":
                onPaperGenerationProgress(event.data as PaperGenerationEvent);
                break;
              case "hw_cost_estimate":
                onHwCostEstimate?.(event.data as HwCostEstimateData);
                break;
              case "hw_cost_actual":
                onHwCostActual?.(event.data as HwCostActualData);
                break;
              case "code_execution_started":
                if (onCodeExecutionStarted) {
                  onCodeExecutionStarted(
                    mapCodeExecutionStartedEvent(event.data as ApiCodeExecutionStartedData)
                  );
                }
                break;
              case "code_execution_completed":
                if (onCodeExecutionCompleted) {
                  const completed = event.data as ApiCodeExecutionCompletedData;
                  onCodeExecutionCompleted({
                    execution_id: completed.execution_id,
                    run_type: completed.run_type ?? "codex_execution",
                    status: completed.status,
                    exec_time: completed.exec_time,
                    completed_at: completed.completed_at,
                  });
                }
                break;
              case "stage_skip_window":
                if (onStageSkipWindow) {
                  onStageSkipWindow(event.data as StageSkipWindowUpdate);
                }
                break;
              case "complete":
                onComplete(event.data.status);
                return;
              case "error":
                onError?.(event.data as string);
                break;
              case "heartbeat":
                break;
            }
          } catch (parseError) {
            // eslint-disable-next-line no-console
            console.warn("Failed to parse SSE event:", line, parseError);
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        return;
      }

      const errorMessage = error instanceof Error ? error.message : "Connection failed";

      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current++;
        // eslint-disable-next-line no-console
        console.debug(
          `[Research Run SSE] Connection failed: ${errorMessage}. Reconnection attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts} in ${delay}ms`
        );
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      } else {
        // eslint-disable-next-line no-console
        console.error(
          "[Research Run SSE] Max reconnection attempts reached. Connection permanently lost."
        );
        onError?.("Max reconnection attempts reached. Please refresh the page.");
      }
    }
  }, [
    enabled,
    conversationId,
    runId,
    ensureInitialSnapshot,
    onStageProgress,
    onLog,
    onArtifact,
    onSubstageCompleted,
    onRunEvent,
    onBestNodeSelection,
    onSubstageSummary,
    onPaperGenerationProgress,
    onComplete,
    onHwCostEstimate,
    onHwCostActual,
    onError,
    onStageSkipWindow,
    onCodeExecutionStarted,
    onCodeExecutionCompleted,
    onReviewCompleted,
  ]);

  useEffect(() => {
    if (enabled && conversationId) {
      connect();
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [enabled, conversationId, connect]);

  const disconnect = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
  }, []);

  useEffect(() => {
    initialSnapshotFetchedRef.current = false;
  }, [runId, conversationId]);

  return {
    disconnect,
  };
}
