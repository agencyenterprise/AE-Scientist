"use client";

import { useCallback, useRef, useState } from "react";
import { apiStream } from "@/shared/lib/api-client";
import type {
  ImportState,
  SSEEvent,
  SSEState,
  SSEProgress,
  SSESectionUpdate,
} from "@/features/conversation-import/types/types";

// Order of sections as streamed from the backend
const SECTION_ORDER = [
  "title",
  "short_hypothesis",
  "related_work",
  "abstract",
  "experiments",
  "expected_outcome",
  "risk_factors_and_limitations",
] as const;

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
  /** Accumulated content organized by section */
  sections: Record<string, string>;
  /** Current import state/phase */
  currentState: ImportState | "";
  /** Summary progress percentage (0-100) */
  summaryProgress: number | null;
  /** Whether this is an update to existing conversation */
  isUpdateMode: boolean;
  /** Whether currently streaming */
  isStreaming: boolean;
  /** Computed streaming content from sections in order */
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
  const [sections, setSections] = useState<Record<string, string>>({});
  const [currentState, setCurrentState] = useState<ImportState | "">("");
  const [summaryProgress, setSummaryProgress] = useState<number | null>(null);
  const [isUpdateMode, setIsUpdateMode] = useState(false);

  // Ref for auto-scrolling
  const streamingRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Compute streaming content from sections in correct order
  const streamingContent = SECTION_ORDER.filter(key => sections[key])
    .map(key => sections[key])
    .join("\n");

  // Reset all streaming state
  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setSections({});
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
      setSections({});
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
              eventData = JSON.parse(line);
            } catch {
              // Skip unparseable lines
              continue;
            }

            switch (eventData.type) {
              case "section_update": {
                const { field, data } = eventData as SSESectionUpdate;
                setSections(prev => ({ ...prev, [field]: data }));
                // Auto-scroll
                if (streamingRef.current) {
                  streamingRef.current.scrollTop = streamingRef.current.scrollHeight;
                }
                break;
              }
              case "state": {
                const stateValue = (eventData as SSEState).data;
                setCurrentState(stateValue);
                if (stateValue !== "summarizing") {
                  setSummaryProgress(null);
                }
                break;
              }
              case "progress": {
                const prog = (eventData as SSEProgress).data;
                if (prog.phase === "summarizing" && prog.total > 0) {
                  const pct = Math.max(
                    0,
                    Math.min(100, Math.round((prog.current / prog.total) * 100))
                  );
                  setSummaryProgress(pct);
                  setCurrentState("summarizing" as ImportState);
                }
                break;
              }
              case "conflict": {
                const conflictEvt = eventData as {
                  type: "conflict";
                  data: {
                    conversations: Array<{
                      id: number;
                      title: string;
                      updated_at: string;
                      url: string;
                    }>;
                  };
                };
                setIsStreaming(false);
                setCurrentState("");
                onEnd?.();
                return {
                  success: false,
                  hasConflict: true,
                  conflicts: conflictEvt.data.conversations,
                };
              }
              case "model_limit_conflict": {
                const mdlEvt = eventData as {
                  type: "model_limit_conflict";
                  data: { message: string; suggestion: string };
                };
                setIsStreaming(false);
                setCurrentState("");
                onEnd?.();
                return {
                  success: false,
                  hasModelLimitConflict: true,
                  modelLimitMessage: mdlEvt.data.message,
                  modelLimitSuggestion: mdlEvt.data.suggestion,
                };
              }
              case "error": {
                const err = eventData as { type: "error"; data: string; code?: string };
                setIsStreaming(false);
                onEnd?.();
                const errorMessage =
                  err.code === "CHAT_NOT_FOUND"
                    ? "This conversation no longer exists or has been deleted. Please check the URL and try again."
                    : err.data;
                onError?.(errorMessage);
                return {
                  success: false,
                  error: errorMessage,
                };
              }
              case "done": {
                const doneEvt = eventData as {
                  type: "done";
                  data: { conversation?: { id: number }; error?: string };
                };
                const conv = doneEvt.data.conversation;
                if (conv && typeof conv.id === "number") {
                  setIsStreaming(false);
                  setIsUpdateMode(false);
                  setCurrentState("");
                  onEnd?.();
                  onSuccess?.(conv.id);
                  if (autoRedirect) {
                    window.location.href = `/conversations/${conv.id}`;
                  }
                  return {
                    success: true,
                    conversationId: conv.id,
                  };
                }
                const errMsg = doneEvt.data.error ?? "Import failed";
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
        // AbortError is expected on cleanup
        if ((error as Error).name === "AbortError") {
          return {
            success: false,
            error: "Import cancelled",
          };
        }

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
      sections,
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
