"use client";

import { useCallback, useEffect, useState } from "react";

import { useStreamingImport } from "@/shared/hooks/use-streaming-import";
import { useImportFormState } from "./use-import-form-state";
import { useImportConflictResolution } from "./use-import-conflict-resolution";
import type { ConflictItem, ImportState } from "../types/types";

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

/**
 * Hook for managing conversation import flow.
 *
 * This is a facade hook that composes:
 * - useImportFormState: URL input and validation
 * - useImportConflictResolution: Conflict handling
 * - useStreamingImport: SSE streaming logic
 *
 * The original API is preserved for backward compatibility while
 * the implementation is now properly split by responsibility.
 */
export function useConversationImport(
  options: UseConversationImportOptions = {}
): UseConversationImportReturn {
  const { onImportStart, onImportEnd, onSuccess, onError, autoRedirect = true } = options;

  // Compose sub-hooks
  const formState = useImportFormState();
  const conflictState = useImportConflictResolution();

  // Model state (kept local as it's tightly coupled with this flow)
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [currentModel, setCurrentModel] = useState("");
  const [currentProvider, setCurrentProvider] = useState("");

  // Streaming import hook
  const streaming = useStreamingImport({
    onStart: onImportStart,
    onEnd: onImportEnd,
    onSuccess,
    onError,
    autoRedirect,
  });

  // Auto-scroll streaming content
  useEffect(() => {
    if (streaming.state.isStreaming && streaming.streamingRef.current) {
      streaming.streamingRef.current.scrollTop = streaming.streamingRef.current.scrollHeight;
    }
  }, [streaming.state.streamingContent, streaming.state.isStreaming, streaming.streamingRef]);

  // Reset all state
  const reset = useCallback(() => {
    formState.actions.reset();
    conflictState.actions.reset();
    streaming.actions.reset();
    setSelectedModel("");
    setSelectedProvider("");
  }, [formState.actions, conflictState.actions, streaming.actions]);

  // Model handlers
  const setModel = useCallback(
    (model: string, provider: string) => {
      formState.actions.clearError();
      if (model && provider) {
        setSelectedModel(model);
        setSelectedProvider(provider);
        setCurrentModel(model);
        setCurrentProvider(provider);
      } else {
        setSelectedModel("");
        setSelectedProvider("");
      }
    },
    [formState.actions]
  );

  const setModelDefaults = useCallback(
    (model: string, provider: string) => {
      if (!selectedModel && !selectedProvider) {
        setCurrentModel(model);
        setCurrentProvider(provider);
      }
    },
    [selectedModel, selectedProvider]
  );

  // Core streaming import function with conflict handling
  const handleStreamingImport = useCallback(
    async (
      trimmedUrl: string,
      duplicateResolution: "prompt" | "update_existing" | "create_new",
      targetConversationId?: number,
      acceptSummarization: boolean = false
    ): Promise<void> => {
      const result = await streaming.actions.startStream({
        url: trimmedUrl,
        model: currentModel,
        provider: currentProvider,
        duplicateResolution,
        targetConversationId,
        acceptSummarization,
      });

      // Handle conflicts detected by the stream
      if (result.hasConflict && result.conflicts) {
        conflictState.actions.setConflict(result.conflicts);
      } else if (result.hasModelLimitConflict) {
        conflictState.actions.setModelLimit(
          result.modelLimitMessage || "",
          result.modelLimitSuggestion || ""
        );
      } else if (result.insufficientCredits) {
        const creditMessage =
          result.error ||
          (result.required
            ? `You need at least ${result.required} credits to refine ideas.`
            : "Insufficient credits to refine ideas.");
        formState.actions.setError(creditMessage);
        onError?.(creditMessage);
      } else if (!result.success && result.error) {
        formState.actions.setError(result.error);
        onError?.(result.error);
      }
    },
    [
      currentModel,
      currentProvider,
      streaming.actions,
      conflictState.actions,
      formState.actions,
      onError,
    ]
  );

  // Start import action
  const startImport = useCallback(async () => {
    const trimmedUrl = formState.state.url.trim();

    if (!formState.actions.validate()) {
      onError?.(formState.state.error);
      return;
    }

    if (!currentModel || !currentProvider) {
      const modelError = "LLM model and provider are required. Please wait for model to load.";
      formState.actions.setError(modelError);
      onError?.(modelError);
      return;
    }

    formState.actions.clearError();

    try {
      await handleStreamingImport(trimmedUrl, "prompt");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to import conversation";
      formState.actions.setError(errorMessage);
      onError?.(errorMessage);
    }
  }, [
    formState.state.url,
    formState.state.error,
    formState.actions,
    currentModel,
    currentProvider,
    handleStreamingImport,
    onError,
  ]);

  // Conflict resolution actions
  const resolveConflictGoTo = useCallback(() => {
    if (conflictState.conflict.selectedId) {
      window.location.href = `/conversations/${conflictState.conflict.selectedId}`;
    }
  }, [conflictState.conflict.selectedId]);

  const resolveConflictUpdate = useCallback(async () => {
    const selectedId = conflictState.conflict.selectedId;
    conflictState.actions.clearConflict();
    formState.actions.clearError();

    try {
      await handleStreamingImport(
        formState.state.url.trim(),
        "update_existing",
        selectedId ?? undefined
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to import conversation";
      formState.actions.setError(errorMessage);
      onError?.(errorMessage);
    }
  }, [
    formState.state.url,
    formState.actions,
    conflictState.conflict.selectedId,
    conflictState.actions,
    handleStreamingImport,
    onError,
  ]);

  const resolveConflictCreateNew = useCallback(async () => {
    conflictState.actions.clearConflict();
    formState.actions.clearError();

    try {
      await handleStreamingImport(formState.state.url.trim(), "create_new");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to import conversation";
      formState.actions.setError(errorMessage);
      onError?.(errorMessage);
    }
  }, [
    formState.state.url,
    formState.actions,
    conflictState.actions,
    handleStreamingImport,
    onError,
  ]);

  const cancelConflict = useCallback(() => {
    conflictState.actions.clearConflict();
    formState.actions.clearError();
  }, [conflictState.actions, formState.actions]);

  // Model limit actions
  const proceedWithSummarization = useCallback(async () => {
    conflictState.actions.clearModelLimit();
    formState.actions.clearError();

    try {
      await handleStreamingImport(formState.state.url.trim(), "create_new", undefined, true);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to import conversation";
      formState.actions.setError(errorMessage);
      onError?.(errorMessage);
    }
  }, [
    formState.state.url,
    formState.actions,
    conflictState.actions,
    handleStreamingImport,
    onError,
  ]);

  const cancelModelLimit = useCallback(() => {
    conflictState.actions.clearModelLimit();
  }, [conflictState.actions]);

  return {
    state: {
      url: formState.state.url,
      error: formState.state.error,
      streamingContent: streaming.state.streamingContent,
      currentState: streaming.state.currentState,
      summaryProgress: streaming.state.summaryProgress,
      isUpdateMode: streaming.state.isUpdateMode,
    },
    model: {
      selected: selectedModel,
      provider: selectedProvider,
      current: currentModel,
      currentProvider,
    },
    conflict: {
      hasConflict: conflictState.conflict.hasConflict,
      items: conflictState.conflict.items,
      selectedId: conflictState.conflict.selectedId,
    },
    modelLimit: {
      hasConflict: conflictState.modelLimit.hasConflict,
      message: conflictState.modelLimit.message,
      suggestion: conflictState.modelLimit.suggestion,
    },
    status: {
      isIdle:
        !streaming.state.isStreaming &&
        !conflictState.conflict.hasConflict &&
        !conflictState.modelLimit.hasConflict,
      isImporting: streaming.state.isStreaming,
      hasError: !!formState.state.error,
      hasConflict: conflictState.conflict.hasConflict,
      hasModelLimitConflict: conflictState.modelLimit.hasConflict,
      canSubmit: !!formState.state.url.trim() && !!currentModel && !streaming.state.isStreaming,
    },
    actions: {
      setUrl: formState.actions.setUrl,
      setModel,
      setModelDefaults,
      startImport,
      selectConflict: conflictState.actions.selectConflict,
      resolveConflictGoTo,
      resolveConflictUpdate,
      resolveConflictCreateNew,
      cancelConflict,
      proceedWithSummarization,
      cancelModelLimit,
      reset,
    },
    streamingRef: streaming.streamingRef,
  };
}
