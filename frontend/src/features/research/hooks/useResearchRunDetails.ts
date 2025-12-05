"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/shared/lib/api-client";
import type {
  ResearchRunDetails,
  ResearchRunInfo,
  StageProgress,
  LogEntry,
  ArtifactMetadata,
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
        ? {
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

  const handleRunUpdate = useCallback((run: ResearchRunInfo) => {
    setDetails(prev => (prev ? { ...prev, run } : null));
  }, []);

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
    onRunUpdate: handleRunUpdate,
    onComplete: handleComplete,
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
