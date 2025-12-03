"use client";

import { useCallback, useState } from "react";
import { getUrlValidationError, validateUrl } from "../utils/urlValidation";

/**
 * Form state for import URL.
 */
export interface ImportFormState {
  /** The import URL */
  url: string;
  /** Validation error message */
  error: string;
}

/**
 * Actions for managing import form state.
 */
export interface ImportFormActions {
  /** Set the import URL */
  setUrl: (url: string) => void;
  /** Set the error message */
  setError: (error: string) => void;
  /** Validate the URL and return whether it's valid */
  validate: () => boolean;
  /** Reset form state */
  reset: () => void;
  /** Clear error only */
  clearError: () => void;
}

/**
 * Return type for the import form state hook.
 */
export interface UseImportFormStateReturn {
  state: ImportFormState;
  actions: ImportFormActions;
}

/**
 * Hook for managing import form state (URL and validation).
 *
 * Extracted from useConversationImport to follow Single Responsibility Principle.
 * Handles URL input and validation logic.
 *
 * @example
 * ```typescript
 * const { state, actions } = useImportFormState();
 *
 * const handleSubmit = () => {
 *   if (actions.validate()) {
 *     // Proceed with import
 *     startImport(state.url);
 *   }
 * };
 *
 * return (
 *   <input
 *     value={state.url}
 *     onChange={(e) => actions.setUrl(e.target.value)}
 *   />
 *   {state.error && <span>{state.error}</span>}
 * );
 * ```
 */
export function useImportFormState(): UseImportFormStateReturn {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const validate = useCallback((): boolean => {
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Please enter a URL");
      return false;
    }
    if (!validateUrl(trimmed)) {
      setError(getUrlValidationError());
      return false;
    }
    return true;
  }, [url]);

  const reset = useCallback(() => {
    setUrl("");
    setError("");
  }, []);

  const clearError = useCallback(() => {
    setError("");
  }, []);

  const handleSetUrl = useCallback((newUrl: string) => {
    setUrl(newUrl);
    // Clear error when user starts typing
    setError("");
  }, []);

  return {
    state: {
      url,
      error,
    },
    actions: {
      setUrl: handleSetUrl,
      setError,
      validate,
      reset,
      clearError,
    },
  };
}
