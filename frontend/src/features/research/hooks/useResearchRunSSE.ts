import { useEffect, useRef, useCallback } from "react";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import type { ResearchRunStreamEvent, ApiComponents } from "@/types";
import type {
  ResearchRunInfo,
  StageProgress,
  ArtifactMetadata,
  ResearchRunDetails,
  PaperGenerationEvent,
  SubstageSummary,
  SubstageEvent,
  HwCostEstimateData,
  HwCostActualData,
  ResearchRunCodeExecution,
  StageSkipWindow,
  StageSkipWindowUpdate,
  LlmReviewResponse,
  TerminationStatusData,
} from "@/types/research";

export type { ResearchRunDetails };

export type InitializationStatusData =
  ApiComponents["schemas"]["ResearchRunInitializationStatusData"];

interface UseResearchRunSSEOptions {
  runId: string;
  conversationId: number | null;
  enabled: boolean;
  onInitialData: (data: ResearchRunDetails) => void;
  onStageProgress: (event: StageProgress) => void;
  onArtifact: (event: ArtifactMetadata) => void;
  onRunUpdate: (run: ResearchRunInfo) => void;
  onPaperGenerationProgress: (event: PaperGenerationEvent) => void;
  onComplete: (status: string) => void;
  onRunEvent?: (event: unknown) => void;
  onTerminationStatus?: (event: TerminationStatusData) => void;
  onSubstageSummary?: (event: SubstageSummary) => void;
  onSubstageCompleted?: (event: SubstageEvent) => void;
  onError?: (error: string) => void;
  onHwCostEstimate?: (event: HwCostEstimateData) => void;
  onHwCostActual?: (event: HwCostActualData) => void;
  onCodeExecutionStarted?: (execution: ResearchRunCodeExecution) => void;
  onCodeExecutionCompleted?: (event: CodeExecutionCompletionEvent) => void;
  onStageSkipWindow?: (event: StageSkipWindowUpdate) => void;
  onReviewCompleted?: (review: LlmReviewResponse) => void;
  onInitializationStatus?: (event: InitializationStatusData) => void;
}

interface UseResearchRunSSEReturn {
  disconnect: () => void;
}

// Use generated type instead of manual definition
type CodeExecutionCompletionEvent = ApiCodeExecutionCompletedData;

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
  const terminationRaw = run as unknown as {
    termination_status?: string;
    termination_last_error?: string | null;
  };
  const termination_status =
    terminationRaw.termination_status === "requested" ||
    terminationRaw.termination_status === "in_progress" ||
    terminationRaw.termination_status === "terminated" ||
    terminationRaw.termination_status === "failed"
      ? terminationRaw.termination_status
      : "none";

  return {
    run_id: run.run_id,
    status: run.status,
    initialization_status:
      (run as unknown as { initialization_status?: string }).initialization_status ?? "pending",
    idea_id: run.idea_id,
    idea_version_id: run.idea_version_id,
    pod_id: run.pod_id,
    pod_name: run.pod_name,
    gpu_type: run.gpu_type,
    cost: (run as unknown as { cost?: number }).cost ?? 0,
    public_ip: run.public_ip ?? null,
    ssh_port: run.ssh_port ?? null,
    pod_host_id: run.pod_host_id ?? null,
    error_message: run.error_message ?? null,
    last_heartbeat_at: run.last_heartbeat_at ?? null,
    heartbeat_failures: run.heartbeat_failures,
    created_at: run.created_at,
    updated_at: run.updated_at,
    start_deadline_at: run.start_deadline_at ?? null,
    termination_status,
    termination_last_error: terminationRaw.termination_last_error ?? null,
    parent_run_id: (run as unknown as { parent_run_id?: string | null }).parent_run_id ?? null,
    restart_count: (run as unknown as { restart_count?: number }).restart_count ?? 0,
    last_restart_at:
      (run as unknown as { last_restart_at?: string | null }).last_restart_at ?? null,
    last_restart_reason:
      (run as unknown as { last_restart_reason?: string | null }).last_restart_reason ?? null,
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
    code: snapshot.code ?? null,
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

  const initialCodeExecutions = (() => {
    const raw = (
      data as unknown as {
        code_executions?: Record<string, ApiCodeExecutionSnapshot | null>;
      }
    ).code_executions;
    if (!raw || typeof raw !== "object") {
      return {};
    }
    const next: Partial<Record<ResearchRunCodeExecution["run_type"], ResearchRunCodeExecution>> =
      {};
    for (const value of Object.values(raw)) {
      const normalized = normalizeCodeExecution(value);
      if (!normalized) {
        continue;
      }
      next[normalized.run_type] = normalized;
    }
    return next as ResearchRunDetails["code_executions"];
  })();

  const childConversations =
    "child_conversations" in data
      ? ((data as { child_conversations?: ResearchRunDetails["child_conversations"] })
          .child_conversations ?? [])
      : [];

  return {
    run: normalizeRunInfo(data.run),
    stage_progress: data.stage_progress.map(normalizeStageProgress),
    substage_events: data.substage_events,
    substage_summaries: getInitialSubstageSummaries(data),
    artifacts: data.artifacts,
    paper_generation_progress: data.paper_generation_progress.map(normalizePaperGenerationEvent),
    tree_viz: data.tree_viz,
    stage_skip_windows: rawStageSkipWindows.map(normalizeStageSkipWindow),
    hw_cost_estimate: initialHwCost,
    hw_cost_actual: initialHwCostActual,
    code_executions: initialCodeExecutions,
    child_conversations: childConversations,
  };
}

export function useResearchRunSSE({
  runId,
  conversationId,
  enabled,
  onInitialData,
  onStageProgress,
  onArtifact,
  onRunUpdate,
  onPaperGenerationProgress,
  onComplete,
  onRunEvent,
  onTerminationStatus,
  onInitializationStatus,
  onHwCostEstimate,
  onHwCostActual,
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
  const isConnectedRef = useRef(false);
  const connectionFailedRef = useRef(false);
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
      isConnectedRef.current = true;
      connectionFailedRef.current = false;
      // eslint-disable-next-line no-console
      console.debug("[Research Run SSE] Connection established");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          isConnectedRef.current = false;
          // Stream ended - this could be due to server disconnect, trigger reconnect
          // eslint-disable-next-line no-console
          console.debug("[Research Run SSE] Stream ended, will reconnect on next read attempt");
          break;
        }

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
              case "initialization_status":
                onInitializationStatus?.(event.data as InitializationStatusData);
                break;
              case "run_event":
                onRunEvent?.(event.data);
                break;
              case "termination_status":
                onTerminationStatus?.(event.data as TerminationStatusData);
                break;
              case "artifact":
                onArtifact(event.data as ArtifactMetadata);
                break;
              case "review_completed":
                onReviewCompleted?.(event.data as LlmReviewResponse);
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
                  onCodeExecutionCompleted(event.data as ApiCodeExecutionCompletedData);
                }
                break;
              case "stage_skip_window":
                if (onStageSkipWindow) {
                  onStageSkipWindow(event.data as StageSkipWindowUpdate);
                }
                break;
              case "complete":
                isConnectedRef.current = false;
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

      // Stream ended without a "complete" event - attempt to reconnect
      // This can happen if the server closes the connection unexpectedly
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current++;
        // Reset snapshot flag so we re-fetch full state on reconnect
        initialSnapshotFetchedRef.current = false;
        // eslint-disable-next-line no-console
        console.debug(
          `[Research Run SSE] Stream ended unexpectedly. Reconnection attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts} in ${delay}ms`
        );
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      } else {
        connectionFailedRef.current = true;
        // eslint-disable-next-line no-console
        console.debug(
          "[Research Run SSE] Max reconnection attempts reached after stream end. Will retry when tab becomes visible."
        );
      }
    } catch (error) {
      isConnectedRef.current = false;

      if ((error as Error).name === "AbortError") {
        return;
      }

      const errorMessage = error instanceof Error ? error.message : "Connection failed";

      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current++;
        // Reset snapshot flag so we re-fetch full state on reconnect
        initialSnapshotFetchedRef.current = false;
        // eslint-disable-next-line no-console
        console.debug(
          `[Research Run SSE] Connection failed: ${errorMessage}. Reconnection attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts} in ${delay}ms`
        );
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      } else {
        connectionFailedRef.current = true;
        // eslint-disable-next-line no-console
        console.error(
          "[Research Run SSE] Max reconnection attempts reached. Will retry when tab becomes visible."
        );
        // Don't show error to user - we'll retry when they return to the tab
      }
    }
  }, [
    enabled,
    conversationId,
    runId,
    ensureInitialSnapshot,
    onStageProgress,
    onInitializationStatus,
    onArtifact,
    onSubstageCompleted,
    onRunEvent,
    onTerminationStatus,
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

  // Auto-reconnect when user returns to the tab
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && enabled && conversationId) {
        // If connection failed or we're not connected, reset attempts and reconnect
        if (connectionFailedRef.current || !isConnectedRef.current) {
          // eslint-disable-next-line no-console
          console.debug("[Research Run SSE] Tab became visible, attempting to reconnect...");
          reconnectAttemptsRef.current = 0;
          connectionFailedRef.current = false;
          // Reset snapshot flag so we re-fetch full state on reconnect
          // This ensures we get all events that occurred while disconnected
          initialSnapshotFetchedRef.current = false;
          connect();
        }
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [enabled, conversationId, connect]);

  const disconnect = useCallback(() => {
    isConnectedRef.current = false;
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
