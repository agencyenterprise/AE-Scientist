"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/shared/lib/api-client-typed";
import { extractStageSlug } from "@/shared/lib/stage-utils";
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
  StageSkipWindow,
  StageSkipWindowUpdate,
  TerminationStatusData,
  LlmReviewResponse,
} from "@/types/research";
import { useResearchRunSSE } from "./useResearchRunSSE";
import type { InitializationStatusData } from "./useResearchRunSSE";

interface UseResearchRunDetailsOptions {
  runId: string;
  onReviewCompleted?: (review: LlmReviewResponse) => void;
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
  stageSkipState: StageSkipStateMap;
  skipPendingStage: string | null;
  handleSkipStage: (stageSlug: string) => Promise<void>;
  seedPending: boolean;
  seedError: string | null;
  handleSeedNewIdea: () => Promise<void>;
}

interface CodeExecutionCompletionPayload {
  execution_id: string;
  run_type: ResearchRunCodeExecution["run_type"];
  status: "success" | "failed";
  exec_time: number;
  completed_at: string;
}

export interface StageSkipStateEntry {
  reason: string | null;
  updatedAt: string;
}

export type StageSkipStateMap = Record<string, StageSkipStateEntry>;

/**
 * Hook that manages research run details state including SSE updates
 */
export function useResearchRunDetails({
  runId,
  onReviewCompleted,
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
  const [stageSkipState, setStageSkipState] = useState<StageSkipStateMap>({});
  const [skipPendingStage, setSkipPendingStage] = useState<string | null>(null);
  const [seedPending, setSeedPending] = useState(false);
  const [seedError, setSeedError] = useState<string | null>(null);
  const router = useRouter();

  // SSE callback handlers
  const syncStageSkipState = useCallback((windows: StageSkipWindow[] | undefined) => {
    if (!windows) {
      setStageSkipState({});
      setSkipPendingStage(null);
      return;
    }
    const next: StageSkipStateMap = {};
    windows.forEach(window => {
      if (window.closed_at) {
        return;
      }
      const slug = extractStageSlug(window.stage);
      if (!slug) {
        return;
      }
      next[slug] = {
        reason: window.opened_reason ?? null,
        updatedAt: window.opened_at,
      };
    });
    setStageSkipState(next);
    setSkipPendingStage(prev => (prev && !next[prev] ? null : prev));
  }, []);

  const handleInitialData = useCallback(
    (data: ResearchRunDetails) => {
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
      syncStageSkipState(data.stage_skip_windows);
    },
    [syncStageSkipState]
  );

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

  // Use a ref to avoid recreating this callback when onReviewCompleted changes
  const onReviewCompletedRef = useRef(onReviewCompleted);
  useEffect(() => {
    onReviewCompletedRef.current = onReviewCompleted;
  }, [onReviewCompleted]);

  // Track mounted state to avoid state updates after unmount (e.g., when user navigates away)
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const handleReviewCompleted = useCallback((review: LlmReviewResponse) => {
    if (onReviewCompletedRef.current) {
      onReviewCompletedRef.current(review);
    }
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
    setDetails(prev => {
      if (!prev) {
        return prev;
      }
      const nextExecutions = {
        ...(prev.code_executions ?? {}),
        [execution.run_type]: execution,
      } as NonNullable<ResearchRunDetails["code_executions"]>;
      return {
        ...prev,
        code_executions: nextExecutions,
      };
    });
  }, []);

  const handleCodeExecutionCompleted = useCallback((event: CodeExecutionCompletionPayload) => {
    setDetails(prev => {
      if (!prev) {
        return prev;
      }
      const existing = prev.code_executions?.[event.run_type];
      if (!existing || existing.execution_id !== event.execution_id) {
        return prev;
      }
      return {
        ...prev,
        code_executions: {
          ...(prev.code_executions ?? {}),
          [event.run_type]: {
            ...existing,
            status: event.status,
            exec_time: event.exec_time,
            completed_at: event.completed_at,
          },
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
          typeof metadata.error_message === "string" ? (metadata.error_message as string) : null;
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
          const { data: treeViz, error: treeVizError } = await api.GET(
            "/api/conversations/{conversation_id}/idea/research-run/{run_id}/tree-viz",
            {
              params: {
                path: { conversation_id: conversationId, run_id: runId },
              },
            }
          );
          if (treeVizError) throw new Error("Failed to fetch tree viz");
          // Note: Artifacts are handled via SSE onArtifact callback, no separate fetch needed
          setDetails(prev =>
            prev
              ? {
                  ...prev,
                  tree_viz: treeViz as TreeVizItem[],
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
        const { data: treeViz, error: treeVizError } = await api.GET(
          "/api/conversations/{conversation_id}/idea/research-run/{run_id}/tree-viz",
          {
            params: {
              path: { conversation_id: conversationId, run_id: runId },
            },
          }
        );
        if (treeVizError) throw new Error("Failed to load tree viz");
        setDetails(prev => (prev ? { ...prev, tree_viz: treeViz as TreeVizItem[] } : prev));
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

  const handleStageSkipWindowUpdate = useCallback((event: StageSkipWindowUpdate) => {
    const slug = extractStageSlug(event.stage);
    if (!slug) {
      return;
    }
    setStageSkipState(prev => {
      const next = { ...prev };
      if (event.state === "opened") {
        next[slug] = {
          reason: event.reason ?? null,
          updatedAt: event.timestamp,
        };
      } else {
        delete next[slug];
      }
      return next;
    });
    if (event.state === "closed") {
      setSkipPendingStage(prev => (prev === slug ? null : prev));
    }
  }, []);

  const handleSSEError = useCallback((errorMsg: string) => {
    // eslint-disable-next-line no-console
    console.error("SSE error:", errorMsg);
  }, []);

  const handleTerminationStatus = useCallback((event: TerminationStatusData) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            run: {
              ...prev.run,
              termination_status: event.status,
              termination_last_error: event.last_error ?? null,
            },
          }
        : null
    );
  }, []);

  const handleInitializationStatus = useCallback((event: InitializationStatusData) => {
    setDetails(prev =>
      prev
        ? {
            ...prev,
            run: {
              ...prev.run,
              initialization_status: event.initialization_status,
              updated_at: event.updated_at,
            },
          }
        : null
    );
  }, []);

  // Use SSE for real-time updates
  useResearchRunSSE({
    runId,
    conversationId,
    enabled:
      !!conversationId &&
      (details?.run.status === "running" ||
        details?.run.status === "initializing" ||
        details?.run.status === "pending" ||
        details?.run.termination_status === "requested" ||
        details?.run.termination_status === "in_progress" ||
        !details),
    onInitialData: handleInitialData,
    onStageProgress: handleStageProgress,
    onLog: handleLog,
    onArtifact: handleArtifact,
    onPaperGenerationProgress: handlePaperGenerationProgress,
    onRunUpdate: handleRunUpdate,
    onComplete: handleComplete,
    onRunEvent: handleRunEvent,
    onTerminationStatus: handleTerminationStatus,
    onInitializationStatus: handleInitializationStatus,
    onHwCostEstimate: handleHwCostEstimate,
    onHwCostActual: handleHwCostActual,
    onBestNodeSelection: handleBestNodeSelection,
    onSubstageSummary: handleSubstageSummary,
    onSubstageCompleted: handleSubstageCompleted,
    onError: handleSSEError,
    onCodeExecutionStarted: handleCodeExecutionStarted,
    onCodeExecutionCompleted: handleCodeExecutionCompleted,
    onStageSkipWindow: handleStageSkipWindowUpdate,
    onReviewCompleted: handleReviewCompleted,
  });

  // Initial load to get conversation_id (SSE takes over after that)
  useEffect(() => {
    const fetchConversationId = async () => {
      try {
        const { data: runInfo, error: runInfoError } = await api.GET(
          "/api/research-runs/{run_id}/",
          {
            params: { path: { run_id: runId } },
          }
        );
        if (runInfoError) throw new Error("Failed to load research run");
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
        const { data: refreshed, error: refreshError } = await api.GET(
          "/api/conversations/{conversation_id}/idea/research-run/{run_id}",
          {
            params: {
              path: { conversation_id: conversationId, run_id: runId },
            },
          }
        );
        if (refreshError) throw new Error("Failed to refresh run details");
        setDetails(refreshed as unknown as ResearchRunDetails);
      } catch (refreshErr) {
        // eslint-disable-next-line no-console
        console.warn("Failed to refresh run details after stop:", refreshErr);
      }
    };
    try {
      setStopError(null);
      setStopPending(true);
      const { error: stopError } = await api.POST(
        "/api/conversations/{conversation_id}/idea/research-run/{run_id}/stop",
        {
          params: {
            path: { conversation_id: conversationId, run_id: runId },
          },
        }
      );
      if (stopError) throw new Error("Failed to stop research run");
      // Best-effort refresh so the UI updates immediately even if SSE is delayed/lost.
      await refreshDetails();
    } catch (err) {
      setStopError(err instanceof Error ? err.message : "Failed to stop research run");
    } finally {
      setStopPending(false);
    }
  }, [conversationId, runId, stopPending]);

  const handleSkipStage = useCallback(
    async (stageSlug: string) => {
      if (!conversationId) {
        throw new Error("Conversation not available yet. Please try again.");
      }
      const { error: skipError } = await api.POST(
        "/api/conversations/{conversation_id}/idea/research-run/{run_id}/skip-stage",
        {
          params: {
            path: { conversation_id: conversationId, run_id: runId },
          },
          body: {
            stage: stageSlug,
          },
        }
      );
      if (skipError) throw new Error("Failed to skip stage");
      setSkipPendingStage(stageSlug);
    },
    [conversationId, runId]
  );

  const handleSeedNewIdea = useCallback(async () => {
    if (!conversationId || seedPending) {
      return;
    }

    try {
      setSeedError(null);
      setSeedPending(true);

      const { data: response, error: seedError } = await api.POST(
        "/api/conversations/{conversation_id}/idea/research-run/{run_id}/seed-new-idea",
        {
          params: {
            path: { conversation_id: conversationId, run_id: runId },
          },
        }
      );

      // Check if component is still mounted before updating state or navigating
      if (!isMountedRef.current) {
        // Component unmounted during API call - operation completed in background
        // User navigated away, so don't try to update state or navigate
        return;
      }

      if (seedError) throw new Error("Failed to seed new idea from this run");

      router.push(`/conversations/${response.conversation_id}`);
    } catch (err) {
      // Only update error state if still mounted and it's not an abort error
      if (isMountedRef.current) {
        const isAbortError = err instanceof Error && err.name === "AbortError";
        if (!isAbortError) {
          setSeedError(
            err instanceof Error ? err.message : "Failed to seed new idea from this run"
          );
        }
      }
    } finally {
      // Only update pending state if still mounted
      if (isMountedRef.current) {
        setSeedPending(false);
      }
    }
  }, [conversationId, runId, seedPending, router]);

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
    stageSkipState,
    skipPendingStage,
    handleSkipStage,
    seedPending,
    seedError,
    handleSeedNewIdea,
  };
}
