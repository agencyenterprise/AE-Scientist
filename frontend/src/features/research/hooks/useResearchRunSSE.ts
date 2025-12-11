import { useEffect, useRef, useCallback, useState } from "react";
import { config } from "@/shared/lib/config";
import type {
  ResearchRunInfo,
  StageProgress,
  LogEntry,
  ArtifactMetadata,
  ResearchRunDetails,
} from "@/types/research";

export type { ResearchRunDetails };

interface SSEEvent {
  type: string;
  data: unknown;
}

interface UseResearchRunSSEOptions {
  runId: string;
  conversationId: number | null;
  enabled: boolean;
  onInitialData: (data: ResearchRunDetails) => void;
  onStageProgress: (event: StageProgress) => void;
  onLog: (event: LogEntry) => void;
  onArtifact: (event: ArtifactMetadata) => void;
  onRunUpdate: (run: ResearchRunInfo) => void;
  onComplete: (status: string) => void;
  onRunEvent?: (event: unknown) => void;
  onError?: (error: string) => void;
}

interface UseResearchRunSSEReturn {
  isConnected: boolean;
  connectionError: string | null;
  reconnect: () => void;
  disconnect: () => void;
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
  onComplete,
  onRunEvent,
  onError,
}: UseResearchRunSSEOptions): UseResearchRunSSEReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

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
      const response = await fetch(
        `${config.apiUrl}/conversations/${conversationId}/idea/research-run/${runId}/events`,
        {
          credentials: "include",
          headers: { Accept: "text/event-stream" },
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
            const event: SSEEvent = JSON.parse(line.slice(6));

            switch (event.type) {
              case "initial":
                onInitialData(event.data as ResearchRunDetails);
                break;
              case "stage_progress":
                onStageProgress(event.data as StageProgress);
                break;
              case "log":
                onLog(event.data as LogEntry);
                break;
              case "artifact":
                onArtifact(event.data as ArtifactMetadata);
                break;
              case "run_update":
                onRunUpdate(event.data as ResearchRunInfo);
                break;
              case "run_event":
                onRunEvent?.(event.data);
                break;
              case "complete":
                onComplete((event.data as { status: string }).status);
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
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      } else {
        onError?.("Max reconnection attempts reached. Please refresh the page.");
      }
    }
  }, [
    enabled,
    conversationId,
    runId,
    onInitialData,
    onStageProgress,
    onLog,
    onArtifact,
    onRunUpdate,
    onRunEvent,
    onComplete,
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

  return {
    isConnected,
    connectionError,
    reconnect: connect,
    disconnect,
  };
}
