"use client";

import { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { LLMPromptCreateRequest, LLMPromptResponse } from "@/types";
import { config } from "@/shared/lib/config";
import { DiffViewer } from "./DiffViewer";
import { PromptTypes } from "@/shared/lib/prompt-types";

interface PromptEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  promptType: string;
}

export function PromptEditModal({
  isOpen,
  onClose,
  promptType,
}: PromptEditModalProps): React.JSX.Element | null {
  const [systemPrompt, setSystemPrompt] = useState<string>("");
  const [isDefault, setIsDefault] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState<boolean>(false);
  const [showDiffView, setShowDiffView] = useState<boolean>(false);
  const [defaultPrompt, setDefaultPrompt] = useState<string>("");
  const [isLoadingDefault, setIsLoadingDefault] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [successMessage, setSuccessMessage] = useState<string>("");
  const [showBackButton, setShowBackButton] = useState<boolean>(false);
  const [isClient, setIsClient] = useState<boolean>(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const applyPromptStateFromResponse = (result: LLMPromptResponse): void => {
    setSystemPrompt(result.system_prompt);
    setIsDefault(result.is_default);
  };

  const fetchCurrentPrompt = useCallback(async (): Promise<LLMPromptResponse | null> => {
    try {
      const response = await fetch(`${config.apiUrl}/llm-prompts/${promptType}`, {
        credentials: "include",
      });

      if (response.ok) {
        const result: LLMPromptResponse = await response.json();
        return result;
      }

      setError("Failed to load prompt");
      return null;
    } catch (err) {
      setError("Failed to load prompt");
      // eslint-disable-next-line no-console
      console.error("Failed to load prompt:", err);
      return null;
    }
  }, [promptType]);

  const loadCurrentPrompt = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError("");

    try {
      const result = await fetchCurrentPrompt();
      if (result) {
        applyPromptStateFromResponse(result);
      }
    } finally {
      setIsLoading(false);
    }
  }, [fetchCurrentPrompt]);

  const loadDefaultPrompt = useCallback(async (): Promise<void> => {
    setIsLoadingDefault(true);
    setError("");

    try {
      const response = await fetch(`${config.apiUrl}/llm-prompts/${promptType}/default`, {
        credentials: "include",
      });

      if (response.ok) {
        const result: LLMPromptResponse = await response.json();
        setDefaultPrompt(result.system_prompt);
      } else {
        setError("Failed to load default prompt");
      }
    } catch (err) {
      setError("Failed to load default prompt");
      // eslint-disable-next-line no-console
      console.error("Failed to load default prompt:", err);
    } finally {
      setIsLoadingDefault(false);
    }
  }, [promptType]);

  // Load prompt when modal opens
  useEffect(() => {
    if (isOpen) {
      // Reset to edit view when modal opens
      setShowDiffView(false);
      setDefaultPrompt("");
      setError("");
      setShowBackButton(false);
      loadCurrentPrompt();
    }
  }, [isOpen, promptType, loadCurrentPrompt]);

  const handleSave = async (): Promise<void> => {
    if (!systemPrompt.trim()) {
      setError("System prompt cannot be empty");
      return;
    }

    setIsSaving(true);
    setError("");

    try {
      const requestData: LLMPromptCreateRequest = {
        prompt_type: promptType,
        system_prompt: systemPrompt.trim(),
      };

      const response = await fetch(`${config.apiUrl}/llm-prompts/${promptType}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(requestData),
      });

      if (response.ok) {
        // Background refresh without spinner to avoid flicker
        const result = await fetchCurrentPrompt();
        if (result) {
          applyPromptStateFromResponse(result);
        }
        setSuccessMessage("Saved");
        setShowBackButton(true);
      } else {
        setError("Failed to save prompt");
      }
    } catch (err) {
      setError("Failed to save prompt");
      // eslint-disable-next-line no-console
      console.error("Failed to save prompt:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRevertToDefault = (): void => {
    setShowConfirmDialog(true);
  };

  const handleConfirmRevert = async (): Promise<void> => {
    setShowConfirmDialog(false);
    setIsDeleting(true);
    setError("");

    try {
      const response = await fetch(`${config.apiUrl}/llm-prompts/${promptType}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (response.ok) {
        // Background refresh without spinner to avoid flicker
        const result = await fetchCurrentPrompt();
        if (result) {
          applyPromptStateFromResponse(result);
        }
        // Show success without closing to avoid flicker
        setSuccessMessage("Reverted to default");
        setShowBackButton(true);
      } else {
        setError("Failed to revert to default");
      }
    } catch (err) {
      const errorMessage = `Failed to revert to default: ${err instanceof Error ? err.message : String(err)}`;
      setError(errorMessage);
      // eslint-disable-next-line no-console
      console.error("Revert to default error:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancelRevert = (): void => {
    setShowConfirmDialog(false);
  };

  const handleShowDiff = async (): Promise<void> => {
    if (!defaultPrompt) {
      await loadDefaultPrompt();
    }
    setShowDiffView(true);
  };

  const handleBackToEdit = (): void => {
    setShowDiffView(false);
  };

  const handleClose = (): void => {
    // Reset all modal state when closing
    setError("");
    setSuccessMessage("");
    setShowBackButton(false);
    setShowConfirmDialog(false);
    setShowDiffView(false);
    setDefaultPrompt("");
    setSystemPrompt("");
    setIsDefault(true);
    onClose();
  };

  const handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === "Escape") {
      handleClose();
    } else if (event.key === "Enter" && event.ctrlKey) {
      handleSave();
    }
  };

  if (!isOpen) return null;
  if (!isClient) return null;

  const getTitleForPromptType = (type: string): string => {
    switch (type) {
      case PromptTypes.IDEA_GENERATION:
        return "Edit import chat prompt";
      case PromptTypes.IDEA_CHAT:
        return "Edit idea refinement prompt";
      default:
        return "Edit prompt";
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
      <div className="relative bg-card rounded-lg p-4 sm:p-6 w-full sm:max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-foreground">
            {showDiffView
              ? "Compare custom and default prompts"
              : getTitleForPromptType(promptType)}
          </h2>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground text-2xl"
            disabled={isSaving || isDeleting}
          >
            ×
          </button>
        </div>

        {/* Status indicator */}
        <div className="mb-4">
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
              isDefault
                ? "bg-[color-mix(in_srgb,var(--primary),transparent_90%)] text-[var(--primary-700)]"
                : "bg-green-100 text-green-800"
            }`}
          >
            {isDefault ? "Using default prompt" : "Using custom prompt"}
          </span>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 text-destructive rounded">
            {error}
          </div>
        )}

        {/* Success message */}
        {successMessage && (
          <div
            className="mb-4 p-3 bg-green-500/10 border border-green-500/30 text-green-400 rounded"
            role="status"
            aria-live="polite"
          >
            {successMessage}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)]"></div>
              <span className="ml-2 text-muted-foreground">Loading prompt...</span>
            </div>
          ) : showDiffView ? (
            <div className="h-full overflow-y-auto">
              {isLoadingDefault ? (
                <div className="flex items-center justify-center h-32">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)]"></div>
                  <span className="ml-2 text-muted-foreground">Loading default prompt...</span>
                </div>
              ) : (
                <DiffViewer
                  original={defaultPrompt}
                  modified={systemPrompt}
                  title="Changes from Default Prompt"
                />
              )}
            </div>
          ) : (
            <div className="h-full space-y-4">
              {/* System Prompt */}
              <div>
                <label
                  htmlFor="system-prompt-editor"
                  className="block text-sm font-medium text-muted-foreground mb-2"
                >
                  System Prompt
                </label>
                <textarea
                  id="system-prompt-editor"
                  value={systemPrompt}
                  onChange={e => setSystemPrompt(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="w-full h-56 sm:h-64 p-3 border border-[var(--border)] rounded-md resize-none focus:ring-2 focus:ring-[var(--ring)] focus:border-[var(--ring)] bg-[var(--surface)] text-[var(--foreground)]"
                  placeholder="Enter the system prompt that defines the AI's role and behavior for this task..."
                  disabled={isSaving || isDeleting}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  This sets the AI&apos;s role and overall behavior for this specific task.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mt-6 pt-4 border-t border-border">
          {showDiffView ? (
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center space-x-3">
                {!isDefault && (
                  <button
                    onClick={handleRevertToDefault}
                    disabled={isDeleting || isSaving || isLoading}
                    className="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isDeleting ? "Reverting..." : "Revert to default"}
                  </button>
                )}
              </div>
              <button
                onClick={handleBackToEdit}
                className="px-4 py-2 text-sm font-medium text-[var(--primary-700)] hover:bg-[var(--muted)] rounded-md flex items-center space-x-1"
              >
                <span>←</span>
                <span>Back to Edit</span>
              </button>
            </div>
          ) : (
            <>
              <div className="flex space-x-3 order-2 sm:order-1">
                {!isDefault && (
                  <>
                    <button
                      onClick={handleRevertToDefault}
                      disabled={isDeleting || isSaving || isLoading}
                      className="px-4 py-2 text-sm font-medium text-destructive hover:text-destructive hover:bg-destructive/10 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isDeleting ? "Reverting..." : "Revert to default"}
                    </button>
                    <button
                      onClick={handleShowDiff}
                      disabled={isDeleting || isSaving || isLoading || isLoadingDefault}
                      className="px-4 py-2 text-sm font-medium text-[var(--primary-700)] hover:bg-[var(--muted)] rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isLoadingDefault ? "Loading..." : "Diff with default"}
                    </button>
                  </>
                )}
              </div>
              <div className="flex space-x-3 order-1 sm:order-2 justify-end">
                <button
                  onClick={handleClose}
                  disabled={isSaving || isDeleting}
                  className="px-4 py-2 text-sm font-medium text-foreground bg-muted hover:bg-muted/80 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {showBackButton ? "Back" : "Cancel"}
                </button>
                <button
                  onClick={handleSave}
                  disabled={isSaving || isDeleting || isLoading || !systemPrompt.trim()}
                  className="px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] bg-[var(--primary)] hover:bg-[var(--primary-hover)] rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? "Saving..." : "Save"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Confirmation Dialog (inside modal to avoid full-screen overlay flicker) */}
      {showConfirmDialog && (
        <>
          <div className="absolute inset-0 z-10 bg-black bg-opacity-20"></div>
          <div className="absolute inset-0 z-20 flex items-center justify-center">
            <div className="bg-card rounded-lg p-6 w-full max-w-md shadow-2xl">
              <h3 className="text-lg font-semibold text-foreground mb-4">
                Revert to Default Prompts
              </h3>
              <p className="text-muted-foreground mb-6">
                Are you sure you want to revert to the default prompts? This will deactivate your
                custom prompts and you&apos;ll need to recreate them if you want to use them again.
              </p>
              <div className="flex justify-end space-x-3">
                <button
                  onClick={handleCancelRevert}
                  disabled={isDeleting}
                  className="px-4 py-2 text-sm font-medium text-foreground bg-muted hover:bg-muted/80 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmRevert}
                  disabled={isDeleting}
                  className="px-4 py-2 text-sm font-medium text-white bg-destructive hover:bg-destructive/90 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isDeleting ? "Reverting..." : "Revert to Default"}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>,
    document.body
  );
}
