"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { config } from "@/shared/lib/config";
import {
  ConflictItem,
  ImportState,
  SSEConflict,
  SSEEvent,
  SSEModelLimit,
  SSEProgress,
  SSEState,
} from "../types/types";
import { getUrlValidationError, validateUrl } from "../utils/urlValidation";

// Re-export ConflictItem for consumers
export type { ConflictItem } from "../types/types";

// Options for the hook
export interface UseConversationImportOptions {
  onImportStart?: () => void;
  onImportEnd?: () => void;
  onSuccess?: (conversationId: number) => void;
  onError?: (error: string) => void;
  autoRedirect?: boolean;
}

// Return type for the hook
export interface UseConversationImportReturn {
  // State
  state: {
    url: string;
    error: string;
    streamingContent: string;
    currentState: ImportState | "";
    summaryProgress: number | null;
    isUpdateMode: boolean;
  };

  // Model state
  model: {
    selected: string;
    provider: string;
    current: string;
    currentProvider: string;
  };

  // Conflict state
  conflict: {
    hasConflict: boolean;
    items: ConflictItem[];
    selectedId: number | null;
  };

  // Model limit state
  modelLimit: {
    hasConflict: boolean;
    message: string;
    suggestion: string;
  };

  // Computed status flags
  status: {
    isIdle: boolean;
    isImporting: boolean;
    hasError: boolean;
    hasConflict: boolean;
    hasModelLimitConflict: boolean;
    canSubmit: boolean;
  };

  // Actions
  actions: {
    setUrl: (url: string) => void;
    setModel: (model: string, provider: string) => void;
    setModelDefaults: (model: string, provider: string) => void;
    startImport: () => Promise<void>;
    selectConflict: (id: number) => void;
    resolveConflictGoTo: () => void;
    resolveConflictUpdate: () => Promise<void>;
    resolveConflictCreateNew: () => Promise<void>;
    cancelConflict: () => void;
    proceedWithSummarization: () => Promise<void>;
    cancelModelLimit: () => void;
    reset: () => void;
  };

  // Ref for streaming textarea auto-scroll
  streamingRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function useConversationImport(
  options: UseConversationImportOptions = {}
): UseConversationImportReturn {
  const { onImportStart, onImportEnd, onSuccess, onError, autoRedirect = true } = options;

  // Form state
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  // Model state
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [currentModel, setCurrentModel] = useState("");
  const [currentProvider, setCurrentProvider] = useState("");

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [currentState, setCurrentState] = useState<ImportState | "">("");
  const [summaryProgress, setSummaryProgress] = useState<number | null>(null);
  const [isUpdateMode, setIsUpdateMode] = useState(false);

  // Conflict state
  const [hasConflict, setHasConflict] = useState(false);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [selectedConflictId, setSelectedConflictId] = useState<number | null>(null);

  // Model limit state
  const [hasModelLimitConflict, setHasModelLimitConflict] = useState(false);
  const [modelLimitMessage, setModelLimitMessage] = useState("");
  const [modelLimitSuggestion, setModelLimitSuggestion] = useState("");

  // Ref for auto-scrolling
  const streamingRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll streaming content
  useEffect(() => {
    if (isStreaming && streamingRef.current) {
      streamingRef.current.scrollTop = streamingRef.current.scrollHeight;
    }
  }, [streamingContent, isStreaming]);

  // Reset all state
  const reset = useCallback(() => {
    setUrl("");
    setError("");
    setStreamingContent("");
    setCurrentState("");
    setSelectedModel("");
    setSelectedProvider("");
    setHasConflict(false);
    setConflicts([]);
    setSelectedConflictId(null);
    setIsUpdateMode(false);
    setHasModelLimitConflict(false);
    setModelLimitMessage("");
    setModelLimitSuggestion("");
    setIsStreaming(false);
    setSummaryProgress(null);
  }, []);

  // Model handlers
  const setModel = useCallback((model: string, provider: string) => {
    setError("");
    if (model && provider) {
      setSelectedModel(model);
      setSelectedProvider(provider);
      setCurrentModel(model);
      setCurrentProvider(provider);
    } else {
      setSelectedModel("");
      setSelectedProvider("");
    }
  }, []);

  const setModelDefaults = useCallback(
    (model: string, provider: string) => {
      if (!selectedModel && !selectedProvider) {
        setCurrentModel(model);
        setCurrentProvider(provider);
      }
    },
    [selectedModel, selectedProvider]
  );

  // Core streaming import function
  const handleStreamingImport = useCallback(
    async (
      trimmedUrl: string,
      duplicateResolution: "prompt" | "update_existing" | "create_new",
      targetConversationId?: number,
      acceptSummarization: boolean = false
    ): Promise<void> => {
      const body =
        targetConversationId !== undefined
          ? {
              url: trimmedUrl,
              llm_model: currentModel,
              llm_provider: currentProvider,
              accept_summarization: acceptSummarization,
              duplicate_resolution: duplicateResolution,
              target_conversation_id: targetConversationId,
            }
          : {
              url: trimmedUrl,
              llm_model: currentModel,
              llm_provider: currentProvider,
              accept_summarization: acceptSummarization,
              duplicate_resolution: duplicateResolution,
            };

      const response = await fetch(`${config.apiUrl}/conversations/import`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedContent = "";
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
          } catch (e) {
            // eslint-disable-next-line no-console
            console.warn("Failed to parse JSON line:", line, "Error:", e);
            continue;
          }

          switch (eventData.type) {
            case "content": {
              const content = (eventData as { type: "content"; data: string }).data;
              accumulatedContent += content;
              setStreamingContent(accumulatedContent);
              break;
            }
            case "state": {
              const stateValue = (eventData as SSEState).data;
              setCurrentState(stateValue);
              if (stateValue !== "summarizing") setSummaryProgress(null);
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
                setCurrentState(ImportState.Summarizing);
              }
              break;
            }
            case "conflict": {
              setIsStreaming(false);
              setCurrentState("");
              const conflictEvt = eventData as SSEConflict;
              const items = conflictEvt.data.conversations;
              setConflicts(items);
              const firstItem = items[0];
              setSelectedConflictId(firstItem ? firstItem.id : null);
              setHasConflict(true);
              onImportEnd?.();
              return;
            }
            case "model_limit_conflict": {
              setIsStreaming(false);
              setCurrentState("");
              const mdlEvt = eventData as SSEModelLimit;
              setModelLimitMessage(mdlEvt.data.message);
              setModelLimitSuggestion(mdlEvt.data.suggestion);
              setHasModelLimitConflict(true);
              onImportEnd?.();
              return;
            }
            case "error": {
              const err = eventData as { type: "error"; data: string; code?: string };
              setIsStreaming(false);
              onImportEnd?.();
              if (err.code === "CHAT_NOT_FOUND") {
                throw new Error(
                  "This conversation no longer exists or has been deleted. Please check the URL and try again."
                );
              }
              throw new Error(err.data);
            }
            case "done": {
              const doneEvt = eventData as {
                type: "done";
                data: { conversation?: { id: number }; error?: string };
              };
              const conv = doneEvt.data.conversation;
              if (conv && typeof conv.id === "number") {
                setUrl("");
                setIsStreaming(false);
                setIsUpdateMode(false);
                setCurrentState("");
                onImportEnd?.();
                onSuccess?.(conv.id);
                if (autoRedirect) {
                  window.location.href = `/conversations/${conv.id}`;
                }
                return;
              }
              const errMsg = doneEvt.data.error ?? "Import failed";
              throw new Error(errMsg);
            }
            default:
              break;
          }
        }
      }
    },
    [currentModel, currentProvider, onImportEnd, onSuccess, autoRedirect]
  );

  // Start import action
  const startImport = useCallback(async () => {
    const trimmedUrl = url.trim();

    if (!validateUrl(trimmedUrl)) {
      setError(getUrlValidationError());
      onError?.(getUrlValidationError());
      return;
    }

    if (!currentModel || !currentProvider) {
      const modelError = "LLM model and provider are required. Please wait for model to load.";
      setError(modelError);
      onError?.(modelError);
      return;
    }

    setError("");
    setIsStreaming(true);
    setIsUpdateMode(false);
    setStreamingContent("");
    setCurrentState("");
    onImportStart?.();

    try {
      await handleStreamingImport(trimmedUrl, "prompt");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to import conversation";
      setError(errorMessage);
      setIsStreaming(false);
      onImportEnd?.();
      onError?.(errorMessage);
    }
  }, [
    url,
    currentModel,
    currentProvider,
    handleStreamingImport,
    onImportStart,
    onImportEnd,
    onError,
  ]);

  // Conflict resolution actions
  const selectConflict = useCallback((id: number) => {
    setSelectedConflictId(id);
  }, []);

  const resolveConflictGoTo = useCallback(() => {
    if (selectedConflictId) {
      window.location.href = `/conversations/${selectedConflictId}`;
    }
  }, [selectedConflictId]);

  const resolveConflictUpdate = useCallback(async () => {
    setHasConflict(false);
    setConflicts([]);
    setSelectedConflictId(null);
    setError("");
    setIsStreaming(true);
    setIsUpdateMode(true);
    setStreamingContent("");
    setCurrentState("");
    onImportStart?.();

    try {
      await handleStreamingImport(url.trim(), "update_existing", selectedConflictId ?? undefined);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to import conversation";
      setError(errorMessage);
      setIsStreaming(false);
      setIsUpdateMode(false);
      onError?.(errorMessage);
    }
  }, [url, selectedConflictId, handleStreamingImport, onImportStart, onError]);

  const resolveConflictCreateNew = useCallback(async () => {
    setHasConflict(false);
    setConflicts([]);
    setSelectedConflictId(null);
    setError("");
    setIsStreaming(true);
    setIsUpdateMode(false);
    setStreamingContent("");
    setCurrentState("");
    onImportStart?.();

    try {
      await handleStreamingImport(url.trim(), "create_new");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to import conversation";
      setError(errorMessage);
      setIsStreaming(false);
      onError?.(errorMessage);
    }
  }, [url, handleStreamingImport, onImportStart, onError]);

  const cancelConflict = useCallback(() => {
    setHasConflict(false);
    setConflicts([]);
    setSelectedConflictId(null);
    setError("");
  }, []);

  // Model limit actions
  const proceedWithSummarization = useCallback(async () => {
    setHasModelLimitConflict(false);
    setError("");
    setIsStreaming(true);
    setIsUpdateMode(false);
    setStreamingContent("");
    setCurrentState("");
    onImportStart?.();

    try {
      await handleStreamingImport(url.trim(), "create_new", undefined, true);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to import conversation";
      setError(errorMessage);
      setIsStreaming(false);
      onError?.(errorMessage);
    }
  }, [url, handleStreamingImport, onImportStart, onError]);

  const cancelModelLimit = useCallback(() => {
    setHasModelLimitConflict(false);
  }, []);

  return {
    state: {
      url,
      error,
      streamingContent,
      currentState,
      summaryProgress,
      isUpdateMode,
    },
    model: {
      selected: selectedModel,
      provider: selectedProvider,
      current: currentModel,
      currentProvider,
    },
    conflict: {
      hasConflict,
      items: conflicts,
      selectedId: selectedConflictId,
    },
    modelLimit: {
      hasConflict: hasModelLimitConflict,
      message: modelLimitMessage,
      suggestion: modelLimitSuggestion,
    },
    status: {
      isIdle: !isStreaming && !hasConflict && !hasModelLimitConflict,
      isImporting: isStreaming,
      hasError: !!error,
      hasConflict,
      hasModelLimitConflict,
      canSubmit: !!url.trim() && !!currentModel && !isStreaming,
    },
    actions: {
      setUrl,
      setModel,
      setModelDefaults,
      startImport,
      selectConflict,
      resolveConflictGoTo,
      resolveConflictUpdate,
      resolveConflictCreateNew,
      cancelConflict,
      proceedWithSummarization,
      cancelModelLimit,
      reset,
    },
    streamingRef,
  };
}
