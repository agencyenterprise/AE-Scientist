import { useEffect, useRef, useCallback, useState } from "react";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import type { ResearchRunStreamEvent } from "@/types";
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
}

interface UseResearchRunSSEReturn {
  isConnected: boolean;
  connectionError: string | null;
  reconnect: () => void;
  disconnect: () => void;
}

type InitialEventData = Extract<ResearchRunStreamEvent, { type: "initial" }>["data"];
type InitialRunInfo = InitialEventData["run"];
type InitialStageProgress = InitialEventData["stage_progress"][number];
type InitialPaperGenerationEvent = InitialEventData["paper_generation_progress"][number];

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
    hw_cost_estimate: initialHwCost,
    hw_cost_actual: initialHwCostActual,
  };
}

export function useResearchRunSSE({
  runId,
  conversationId,
  enabled,
  onInitialData,
  onStageProgress,
  onLog,
  onArtifact: _onArtifact,
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
}: UseResearchRunSSEOptions): UseResearchRunSSEReturn {
  void _onArtifact;
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
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
    setConnectionError(null);
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

      setIsConnected(true);
      setConnectionError(null);
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
              case "complete":
                onComplete(event.data.status);
                setIsConnected(false);
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

      setIsConnected(false);
      const errorMessage = error instanceof Error ? error.message : "Connection failed";
      setConnectionError(errorMessage);

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
    onSubstageCompleted,
    onRunEvent,
    onBestNodeSelection,
    onSubstageSummary,
    onPaperGenerationProgress,
    onComplete,
    onHwCostEstimate,
    onHwCostActual,
    onError,
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
    setIsConnected(false);
  }, []);

  useEffect(() => {
    initialSnapshotFetchedRef.current = false;
  }, [runId, conversationId]);

  return {
    isConnected,
    connectionError,
    reconnect: connect,
    disconnect,
  };
}
