"use client";

import { useCallback, useRef, useState } from "react";
import * as Sentry from "@sentry/nextjs";
import { apiStream, ApiError } from "@/shared/lib/api-client";
import { ImportState } from "@/features/conversation-import/types/types";
import type { SSEEvent } from "@/features/conversation-import/types/types";
import { parseInsufficientBalanceError } from "@/shared/utils/costs";

/**
 * Options for the streaming import hook.
 */
export interface StreamingImportOptions {
  /** Called when import starts */
  onStart?: () => void;
  /** Called when import ends (success or error) */
  onEnd?: () => void;
  /** Called on successful completion with conversation ID */
  onSuccess?: (conversationId: number) => void;
  /** Called on error */
  onError?: (error: string) => void;
  /** Whether to auto-redirect on success (default: true) */
  autoRedirect?: boolean;
}

/**
 * State returned by the streaming import hook.
 */
export interface StreamingImportState {
  /** Current import state/phase */
  currentState: ImportState | "";
  /** Summary progress percentage (0-100) */
  summaryProgress: number | null;
  /** Whether this is an update to existing conversation */
  isUpdateMode: boolean;
  /** Whether currently streaming */
  isStreaming: boolean;
  /** Streaming markdown content */
  streamingContent: string;
}

/**
 * Parameters for starting a streaming import.
 */
export interface StreamingImportParams {
  /** URL to import from */
  url: string;
  /** LLM model name */
  model: string;
  /** LLM provider */
  provider: string;
  /** How to handle duplicate conversations */
  duplicateResolution: "prompt" | "update_existing" | "create_new";
  /** Target conversation ID for updates */
  targetConversationId?: number;
  /** Whether to accept summarization for model limits */
  acceptSummarization?: boolean;
}

/**
 * Actions returned by the streaming import hook.
 */
export interface StreamingImportActions {
  /** Start the streaming import */
  startStream: (params: StreamingImportParams) => Promise<StreamImportResult>;
  /** Reset all streaming state */
  reset: () => void;
}

/**
 * Result of the streaming import.
 */
export interface StreamImportResult {
  /** Whether the import completed successfully */
  success: boolean;
  /** Conversation ID if successful */
  conversationId?: number;
  /** Error message if failed */
  error?: string;
  /** Whether a conflict was detected */
  hasConflict?: boolean;
  /** Conflict conversations if any */
  conflicts?: Array<{ id: number; title: string; updated_at: string; url: string }>;
  /** Whether a model limit conflict was detected */
  hasModelLimitConflict?: boolean;
  /** Model limit message */
  modelLimitMessage?: string;
  /** Model limit suggestion */
  modelLimitSuggestion?: string;
  /** Whether the request failed due to insufficient balance */
  insufficientBalance?: boolean;
  required?: number;
  available?: number;
  action?: string;
}

/**
 * Return type for the streaming import hook.
 */
export interface StreamingImportReturn {
  state: StreamingImportState;
  actions: StreamingImportActions;
  /** Ref for auto-scrolling textarea */
  streamingRef: React.RefObject<HTMLTextAreaElement | null>;
}

/**
 * Base hook for streaming import operations.
 *
 * Handles the common streaming logic for importing conversations,
 * including section updates, progress tracking, and conflict detection.
 *
 * This hook provides the foundation for useConversationImport and
 * useManualIdeaImport, handling the SSE streaming and state management.
 *
 * @example
 * ```typescript
 * const { state, actions, streamingRef } = useStreamingImport({
 *   onSuccess: (conversationId) => {
 *     router.push(`/conversations/${conversationId}`);
 *   },
 *   onError: (error) => {
 *     console.error('Import failed:', error);
 *   },
 * });
 *
 * const handleImport = async () => {
 *   const result = await actions.startStream({
 *     url: importUrl,
 *     model: 'gpt-4',
 *     provider: 'openai',
 *     duplicateResolution: 'prompt',
 *   });
 *
 *   if (result.hasConflict) {
 *     // Handle conflict...
 *   }
 * };
 * ```
 */
export function useStreamingImport(options: StreamingImportOptions = {}): StreamingImportReturn {
  const { onStart, onEnd, onSuccess, onError, autoRedirect = true } = options;

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState<string>("");
  const [currentState, setCurrentState] = useState<ImportState | "">("");
  const [summaryProgress, setSummaryProgress] = useState<number | null>(null);
  const [isUpdateMode, setIsUpdateMode] = useState(false);

  // Ref for auto-scrolling
  const streamingRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Reset all streaming state
  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStreamingContent("");
    setCurrentState("");
    setSummaryProgress(null);
    setIsUpdateMode(false);
    setIsStreaming(false);
  }, []);

  // Start the streaming import
  const startStream = useCallback(
    async (params: StreamingImportParams): Promise<StreamImportResult> => {
      const {
        url,
        model,
        provider,
        duplicateResolution,
        targetConversationId,
        acceptSummarization = false,
      } = params;

      // Reset state for new stream
      setStreamingContent("");
      setCurrentState("");
      setSummaryProgress(null);
      setIsStreaming(true);
      setIsUpdateMode(duplicateResolution === "update_existing");
      onStart?.();

      // Abort any previous stream
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const body: Record<string, unknown> = {
        url,
        llm_model: model,
        llm_provider: provider,
        accept_summarization: acceptSummarization,
        duplicate_resolution: duplicateResolution,
      };

      if (targetConversationId !== undefined) {
        body.target_conversation_id = targetConversationId;
      }

      try {
        const response = await apiStream("/conversations/import", {
          method: "POST",
          headers: { Accept: "text/event-stream" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!response.body) {
          throw new Error("No response body");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.trim()) continue;

            let eventData: SSEEvent;
            try {
              eventData = JSON.parse(line) as SSEEvent;
            } catch {
              continue;
            }

            switch (eventData.type) {
              case "markdown_delta": {
                const chunk = eventData.data;
                if (typeof chunk === "string") {
                  setStreamingContent(prev => prev + chunk);
                  if (streamingRef.current) {
                    streamingRef.current.scrollTop = streamingRef.current.scrollHeight;
                  }
                }
                break;
              }
              case "state": {
                const stateValue = eventData.data as ImportState;
                setCurrentState(stateValue);
                if (stateValue !== ImportState.Summarizing) {
                  setSummaryProgress(null);
                }
                break;
              }
              case "progress": {
                const progress = eventData.data;
                if (progress.phase === "summarizing" && progress.total > 0) {
                  const pct = Math.max(
                    0,
                    Math.min(100, Math.round((progress.current / progress.total) * 100))
                  );
                  setSummaryProgress(pct);
                  setCurrentState(ImportState.Summarizing);
                }
                break;
              }
              case "conflict": {
                setIsStreaming(false);
                setCurrentState("");
                onEnd?.();
                return {
                  success: false,
                  hasConflict: true,
                  conflicts: eventData.data.conversations,
                };
              }
              case "model_limit_conflict": {
                setIsStreaming(false);
                setCurrentState("");
                onEnd?.();
                return {
                  success: false,
                  hasModelLimitConflict: true,
                  modelLimitMessage: eventData.data.message,
                  modelLimitSuggestion: eventData.data.suggestion ?? "",
                };
              }
              case "error": {
                setIsStreaming(false);
                onEnd?.();
                const errorMessage =
                  eventData.code === "CHAT_NOT_FOUND"
                    ? "This conversation no longer exists or has been deleted. Please check the URL and try again."
                    : eventData.data;
                onError?.(errorMessage);
                return {
                  success: false,
                  error: errorMessage,
                };
              }
              case "done": {
                // Validate that data is an object with expected shape
                if (
                  typeof eventData.data !== "object" ||
                  eventData.data === null ||
                  !("conversation" in eventData.data || "error" in eventData.data)
                ) {
                  // Malformed "done" event - throw error so Sentry captures it
                  throw new Error(
                    `Malformed "done" event: expected object with conversation/error, got ${typeof eventData.data}`
                  );
                }

                const { conversation, error } = eventData.data;
                if (conversation && typeof conversation.id === "number") {
                  setIsStreaming(false);
                  setIsUpdateMode(false);
                  setCurrentState("");
                  onEnd?.();
                  onSuccess?.(conversation.id);
                  if (autoRedirect) {
                    window.location.href = `/conversations/${conversation.id}`;
                  }
                  return {
                    success: true,
                    conversationId: conversation.id,
                  };
                }
                const errMsg = error ?? "Import failed";
                setIsStreaming(false);
                onEnd?.();
                onError?.(errMsg);
                return {
                  success: false,
                  error: errMsg,
                };
              }
              default:
                break;
            }
          }
        }

        // Stream ended without done event
        setIsStreaming(false);
        onEnd?.();
        return {
          success: false,
          error: "Stream ended unexpectedly",
        };
      } catch (error) {
        if (error instanceof ApiError && error.status === 402) {
          const info = parseInsufficientBalanceError(error.data);
          const message = info?.message || "Insufficient balance. Please add funds to continue.";
          setIsStreaming(false);
          onEnd?.();
          onError?.(message);
          return {
            success: false,
            error: message,
            insufficientBalance: true,
            required: info?.required_cents,
            available: info?.available_cents,
            action: info?.action,
          };
        }
        // AbortError is expected on cleanup
        if ((error as Error).name === "AbortError") {
          return {
            success: false,
            error: "Import cancelled",
          };
        }

        // Report unexpected errors to Sentry
        Sentry.captureException(error, {
          tags: {
            feature: "conversation-import",
            stream_phase: "streaming",
          },
          extra: {
            url,
            model,
            provider,
          },
        });

        const errorMessage =
          error instanceof Error ? error.message : "Failed to import conversation";
        setIsStreaming(false);
        onEnd?.();
        onError?.(errorMessage);
        return {
          success: false,
          error: errorMessage,
        };
      }
    },
    [onStart, onEnd, onSuccess, onError, autoRedirect]
  );

  return {
    state: {
      currentState,
      summaryProgress,
      isUpdateMode,
      isStreaming,
      streamingContent,
    },
    actions: {
      startStream,
      reset,
    },
    streamingRef,
  };
}
