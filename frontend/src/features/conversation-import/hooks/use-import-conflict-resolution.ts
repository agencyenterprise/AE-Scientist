"use client";

import { useCallback, useState } from "react";
import type { ConflictItem } from "../types/types";

/**
 * State for conflict detection.
 */
export interface ConflictState {
  /** Whether a duplicate conflict was detected */
  hasConflict: boolean;
  /** List of conflicting conversations */
  items: ConflictItem[];
  /** Currently selected conflict ID */
  selectedId: number | null;
}

/**
 * State for model limit conflicts.
 */
export interface ModelLimitState {
  /** Whether a model limit conflict was detected */
  hasConflict: boolean;
  /** Message explaining the model limit */
  message: string;
  /** Suggested action */
  suggestion: string;
}

/**
 * Actions for managing conflict resolution state.
 */
export interface ConflictActions {
  /** Set conflict items */
  setConflict: (items: ConflictItem[]) => void;
  /** Select a conflict by ID */
  selectConflict: (id: number) => void;
  /** Clear conflict state */
  clearConflict: () => void;
  /** Set model limit conflict */
  setModelLimit: (message: string, suggestion: string) => void;
  /** Clear model limit conflict */
  clearModelLimit: () => void;
  /** Reset all conflict state */
  reset: () => void;
}

/**
 * Return type for the import conflict resolution hook.
 */
export interface UseImportConflictResolutionReturn {
  conflict: ConflictState;
  modelLimit: ModelLimitState;
  actions: ConflictActions;
}

/**
 * Hook for managing import conflict resolution state.
 *
 * Extracted from useConversationImport to follow Single Responsibility Principle.
 * Handles duplicate conversation conflicts and model limit conflicts.
 *
 * @example
 * ```typescript
 * const { conflict, modelLimit, actions } = useImportConflictResolution();
 *
 * // When a conflict is detected from the stream
 * if (streamResult.hasConflict) {
 *   actions.setConflict(streamResult.conflicts);
 * }
 *
 * // When user resolves conflict
 * const handleGoToExisting = () => {
 *   window.location.href = `/conversations/${conflict.selectedId}`;
 * };
 *
 * const handleCreateNew = () => {
 *   actions.clearConflict();
 *   startImport('create_new');
 * };
 * ```
 */
export function useImportConflictResolution(): UseImportConflictResolutionReturn {
  // Duplicate conflict state
  const [hasConflict, setHasConflict] = useState(false);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [selectedConflictId, setSelectedConflictId] = useState<number | null>(null);

  // Model limit state
  const [hasModelLimitConflict, setHasModelLimitConflict] = useState(false);
  const [modelLimitMessage, setModelLimitMessage] = useState("");
  const [modelLimitSuggestion, setModelLimitSuggestion] = useState("");

  const setConflict = useCallback((items: ConflictItem[]) => {
    setConflicts(items);
    setSelectedConflictId(items[0]?.id ?? null);
    setHasConflict(true);
  }, []);

  const selectConflict = useCallback((id: number) => {
    setSelectedConflictId(id);
  }, []);

  const clearConflict = useCallback(() => {
    setHasConflict(false);
    setConflicts([]);
    setSelectedConflictId(null);
  }, []);

  const setModelLimit = useCallback((message: string, suggestion: string) => {
    setModelLimitMessage(message);
    setModelLimitSuggestion(suggestion);
    setHasModelLimitConflict(true);
  }, []);

  const clearModelLimit = useCallback(() => {
    setHasModelLimitConflict(false);
    setModelLimitMessage("");
    setModelLimitSuggestion("");
  }, []);

  const reset = useCallback(() => {
    setHasConflict(false);
    setConflicts([]);
    setSelectedConflictId(null);
    setHasModelLimitConflict(false);
    setModelLimitMessage("");
    setModelLimitSuggestion("");
  }, []);

  return {
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
    actions: {
      setConflict,
      selectConflict,
      clearConflict,
      setModelLimit,
      clearModelLimit,
      reset,
    },
  };
}
