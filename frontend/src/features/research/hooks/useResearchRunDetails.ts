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
  isConnected: boolean;
  connectionError: string | null;
  stopPending: boolean;
  stopError: string | null;
  handleStopRun: () => Promise<void>;
  reconnect: () => void;
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
  const [stopPending, setStopPending] = useState(false);
  const [stopError, setStopError] = useState<string | null>(null);

  // SSE callback handlers
  const handleInitialData = useCallback((data: ResearchRunDetails) => {
    setDetails(data);
    setLoading(false);
    setError(null);
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

  const handleRunUpdate = useCallback((run: ResearchRunInfo) => {
    setDetails(prev => (prev ? { ...prev, run } : null));
  }, []);

  const handleRunEvent = useCallback(
    async (event: { event_type?: string } | unknown) => {
      if (
        !conversationId ||
        !event ||
        typeof event !== "object" ||
        (event as { event_type?: string }).event_type !== "tree_viz_stored"
      ) {
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
    },
    [conversationId, runId]
  );

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
          }
        : null
    );
  }, []);

  const handleSSEError = useCallback((errorMsg: string) => {
    // eslint-disable-next-line no-console
    console.error("SSE error:", errorMsg);
  }, []);

  // Use SSE for real-time updates
  const { isConnected, connectionError, reconnect } = useResearchRunSSE({
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
    onBestNodeSelection: handleBestNodeSelection,
    onError: handleSSEError,
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
    try {
      setStopError(null);
      setStopPending(true);
      await apiFetch(`/conversations/${conversationId}/idea/research-run/${runId}/stop`, {
        method: "POST",
      });
      // SSE will automatically receive the status update
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
    isConnected,
    connectionError,
    stopPending,
    stopError,
    handleStopRun,
    reconnect,
  };
}
