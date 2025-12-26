"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/shared/lib/api-client";
import type {
  ResearchRunDetails,
  ResearchRunInfo,
  StageProgress,
  LogEntry,
  ArtifactMetadata,
  PaperGenerationEvent,
  TreeVizItem,
  BestNodeSelection,
  SubstageSummary,
  SubstageEvent,
  HwCostEstimateData,
  HwCostActualData,
  ResearchRunCodeExecution,
} from "@/types/research";
import { useResearchRunSSE } from "./useResearchRunSSE";

interface UseResearchRunDetailsOptions {
  runId: string;
}

interface UseResearchRunDetailsReturn {
  details: ResearchRunDetails | null;
  loading: boolean;
  error: string | null;
  conversationId: number | null;
  hwEstimatedCostCents: number | null;
  hwActualCostCents: number | null;
  hwCostPerHourCents: number | null;
  stopPending: boolean;
  stopError: string | null;
  handleStopRun: () => Promise<void>;
}

interface CodeExecutionCompletionPayload {
  execution_id: string;
  status: "success" | "failed";
  exec_time: number;
  completed_at: string;
}

/**
 * Hook that manages research run details state including SSE updates
 */
export function useResearchRunDetails({
  runId,
}: UseResearchRunDetailsOptions): UseResearchRunDetailsReturn {
  const [details, setDetails] = useState<ResearchRunDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [hwEstimatedCostCents, setHwEstimatedCostCents] = useState<number | null>(null);
  const [hwActualCostCents, setHwActualCostCents] = useState<number | null>(null);
  const [hwCostPerHourCents, setHwCostPerHourCents] = useState<number | null>(null);
  const [stopPending, setStopPending] = useState(false);
  const [stopError, setStopError] = useState<string | null>(null);

  // SSE callback handlers
  const handleInitialData = useCallback((data: ResearchRunDetails) => {
    setDetails(data);
    setLoading(false);
    setError(null);
    if (data.hw_cost_estimate) {
      setHwEstimatedCostCents(data.hw_cost_estimate.hw_estimated_cost_cents);
      setHwCostPerHourCents(data.hw_cost_estimate.hw_cost_per_hour_cents);
    }
    if (data.hw_cost_actual) {
      setHwActualCostCents(data.hw_cost_actual.hw_actual_cost_cents);
    }
  }, []);

  const handleStageProgress = useCallback((event: StageProgress) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            stage_progress: [...prev.stage_progress, event],
          }
        : null
    );
  }, []);

  const handleLog = useCallback((event: LogEntry) => {
    setDetails(prev =>
      prev
        ? prev.logs.some(log => log.id === event.id)
          ? prev
          : {
              ...prev,
              logs: [event, ...prev.logs],
            }
        : null
    );
  }, []);

  const handleArtifact = useCallback((event: ArtifactMetadata) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            artifacts: [...prev.artifacts, event],
          }
        : null
    );
  }, []);

  const handlePaperGenerationProgress = useCallback((event: PaperGenerationEvent) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            paper_generation_progress: [...prev.paper_generation_progress, event],
          }
        : null
    );
  }, []);

  const handleBestNodeSelection = useCallback((event: BestNodeSelection) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            best_node_selections: [...(prev.best_node_selections ?? []), event],
          }
        : null
    );
  }, []);

  const handleCodeExecutionStarted = useCallback((execution: ResearchRunCodeExecution) => {
    setDetails(prev => (prev ? { ...prev, code_execution: execution } : prev));
  }, []);

  const handleCodeExecutionCompleted = useCallback((event: CodeExecutionCompletionPayload) => {
    setDetails(prev => {
      if (!prev?.code_execution) {
        return prev;
      }
      if (prev.code_execution.execution_id !== event.execution_id) {
        return prev;
      }
      return {
        ...prev,
        code_execution: {
          ...prev.code_execution,
          status: event.status,
          exec_time: event.exec_time,
          completed_at: event.completed_at,
        },
      };
    });
  }, []);

  const handleSubstageSummary = useCallback((event: SubstageSummary) => {
    setDetails(prev =>
      prev
        ? prev.substage_summaries.some(summary => summary.id === event.id)
          ? prev
          : {
              ...prev,
              substage_summaries: [...prev.substage_summaries, event],
            }
        : null
    );
  }, []);

  const handleRunUpdate = useCallback((run: ResearchRunInfo) => {
    setDetails(prev => (prev ? { ...prev, run } : null));
  }, []);

  const handleRunEvent = useCallback(
    async (event: { event_type?: string; metadata?: Record<string, unknown> } | unknown) => {
      if (!event || typeof event !== "object") {
        return;
      }
      const eventType = (event as { event_type?: string }).event_type;
      if (eventType === "status_changed") {
        const metadata = (event as { metadata?: Record<string, unknown> }).metadata ?? {};
        const toStatus =
          typeof metadata.to_status === "string" ? (metadata.to_status as string) : null;
        const nextDeadline =
          typeof metadata.start_deadline_at === "string"
            ? (metadata.start_deadline_at as string)
            : null;
        const errorMessage =
          typeof metadata.error_message === "string"
            ? (metadata.error_message as string)
            : null;
        if (!toStatus) {
          return;
        }
        setDetails(prev =>
          prev
            ? {
                ...prev,
                run: {
                  ...prev.run,
                  status: toStatus,
                  start_deadline_at: nextDeadline ?? prev.run.start_deadline_at,
                  error_message: errorMessage ?? prev.run.error_message,
                },
              }
            : prev
        );
        return;
      }
      if (eventType === "tree_viz_stored") {
        if (!conversationId) {
          return;
        }
        try {
          const treeViz = await apiFetch<TreeVizItem[]>(
            `/conversations/${conversationId}/idea/research-run/${runId}/tree-viz`
          );
          let artifacts: ArtifactMetadata[] | null = null;
          try {
            artifacts = await apiFetch<ArtifactMetadata[]>(
              `/conversations/${conversationId}/idea/research-run/${runId}/artifacts`
            );
          } catch (artifactErr) {
            // Ignore artifact fetch failures (e.g., 404 when not yet available)
            // eslint-disable-next-line no-console
            console.warn("Artifacts not refreshed after tree viz SSE:", artifactErr);
          }
          setDetails(prev =>
            prev
              ? {
                  ...prev,
                  tree_viz: treeViz,
                  artifacts: artifacts ?? prev.artifacts,
                }
              : prev
          );
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error("Failed to refresh tree viz", err);
        }
        return;
      }

      if (eventType === "pod_billing_summary") {
        const metadata = (event as { metadata?: Record<string, unknown> }).metadata ?? {};
        let cents: number | null = null;
        if (typeof metadata.actual_cost_cents === "number") {
          cents = metadata.actual_cost_cents;
        } else if (typeof metadata.amount === "number") {
          cents = Math.round(metadata.amount * 100);
        } else if (typeof metadata.amount === "string") {
          const numeric = Number(metadata.amount);
          if (!Number.isNaN(numeric)) {
            cents = Math.round(numeric * 100);
          }
        }
        if (cents !== null) {
          setHwActualCostCents(cents);
        }
        return;
      }
    },
    [conversationId, runId]
  );

  const handleHwCostEstimate = useCallback((event: HwCostEstimateData) => {
    setHwEstimatedCostCents(event.hw_estimated_cost_cents);
    setHwCostPerHourCents(event.hw_cost_per_hour_cents);
  }, []);

  const handleHwCostActual = useCallback((event: HwCostActualData) => {
    setHwActualCostCents(event.hw_actual_cost_cents);
    setDetails(prev => (prev ? { ...prev, hw_cost_actual: event } : prev));
  }, []);

  // Ensure tree viz is loaded when details are present but tree_viz is missing/empty
  const treeVizFetchAttempted = useRef(false);
  useEffect(() => {
    if (!conversationId || !details) return;
    if (details.tree_viz && details.tree_viz.length > 0) {
      treeVizFetchAttempted.current = true;
      return;
    }
    if (treeVizFetchAttempted.current) return;
    const fetchTreeViz = async () => {
      treeVizFetchAttempted.current = true;
      try {
        const treeViz = await apiFetch<TreeVizItem[]>(
          `/conversations/${conversationId}/idea/research-run/${runId}/tree-viz`
        );
        setDetails(prev => (prev ? { ...prev, tree_viz: treeViz } : prev));
      } catch (err) {
        // eslint-disable-next-line no-console
        console.error("Failed to load tree viz", err);
      }
    };
    fetchTreeViz();
  }, [conversationId, details, runId]);

  const handleComplete = useCallback((status: string) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            run: { ...prev.run, status },
            code_execution: null,
          }
        : null
    );
  }, []);

  const handleSubstageCompleted = useCallback((event: SubstageEvent) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            substage_events: [...prev.substage_events, event],
          }
        : null
    );
  }, []);

  const handleSSEError = useCallback((errorMsg: string) => {
    // eslint-disable-next-line no-console
    console.error("SSE error:", errorMsg);
  }, []);

  // Use SSE for real-time updates
  useResearchRunSSE({
    runId,
    conversationId,
    enabled:
      !!conversationId &&
      (details?.run.status === "running" || details?.run.status === "pending" || !details),
    onInitialData: handleInitialData,
    onStageProgress: handleStageProgress,
    onLog: handleLog,
    onArtifact: handleArtifact,
    onPaperGenerationProgress: handlePaperGenerationProgress,
    onRunUpdate: handleRunUpdate,
    onComplete: handleComplete,
    onRunEvent: handleRunEvent,
    onHwCostEstimate: handleHwCostEstimate,
    onHwCostActual: handleHwCostActual,
    onBestNodeSelection: handleBestNodeSelection,
    onSubstageSummary: handleSubstageSummary,
    onSubstageCompleted: handleSubstageCompleted,
    onError: handleSSEError,
    onCodeExecutionStarted: handleCodeExecutionStarted,
    onCodeExecutionCompleted: handleCodeExecutionCompleted,
  });

  // Initial load to get conversation_id (SSE takes over after that)
  useEffect(() => {
    const fetchConversationId = async () => {
      try {
        const runInfo = await apiFetch<{ run_id: string; conversation_id: number }>(
          `/research-runs/${runId}/`
        );
        setConversationId(runInfo.conversation_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load research run");
        setLoading(false);
      }
    };
    fetchConversationId();
  }, [runId]);

  const handleStopRun = useCallback(async () => {
    if (!conversationId || stopPending) {
      return;
    }
    const refreshDetails = async () => {
      try {
        const refreshed = await apiFetch<ResearchRunDetails>(
          `/conversations/${conversationId}/idea/research-run/${runId}`
        );
        setDetails(refreshed);
      } catch (refreshErr) {
        // eslint-disable-next-line no-console
        console.warn("Failed to refresh run details after stop:", refreshErr);
      }
    };
    try {
      setStopError(null);
      setStopPending(true);
      await apiFetch(`/conversations/${conversationId}/idea/research-run/${runId}/stop`, {
        method: "POST",
      });
      // Best-effort refresh so the UI updates immediately even if SSE is delayed/lost.
      await refreshDetails();
    } catch (err) {
      setStopError(err instanceof Error ? err.message : "Failed to stop research run");
    } finally {
      setStopPending(false);
    }
  }, [conversationId, runId, stopPending]);

  return {
    details,
    loading,
    error,
    conversationId,
    hwEstimatedCostCents,
    hwActualCostCents,
    hwCostPerHourCents,
    stopPending,
    stopError,
    handleStopRun,
  };
}
