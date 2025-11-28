"use client";

import React from "react";
import { Settings, X, Loader2 } from "lucide-react";

import { ModelSelector } from "@/features/model-selector/components/ModelSelector";
import { PromptTypes } from "@/shared/lib/prompt-types";

export interface ImportFormProps {
  url: string;
  onUrlChange: (url: string) => void;
  error: string;
  model: {
    selected: string;
    provider: string;
    current: string;
    currentProvider: string;
  };
  onModelChange: (model: string, provider: string) => void;
  onModelDefaults: (model: string, provider: string) => void;
  onSubmit: () => void;
  onShowPromptModal?: () => void;
  onClose?: () => void;
  isDisabled?: boolean;
  isSubmitting?: boolean;
  variant?: "modal" | "inline";
  className?: string;
}

/**
 * Form component for importing conversations.
 * Contains URL input, model selector, and submit button.
 * Can be used in modal or inline contexts.
 */
export function ImportForm({
  url,
  onUrlChange,
  error,
  model,
  onModelChange,
  onModelDefaults,
  onSubmit,
  onShowPromptModal,
  onClose,
  isDisabled = false,
  isSubmitting = false,
  variant = "modal",
  className = "",
}: ImportFormProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  const isFormDisabled = isDisabled || isSubmitting || !model.current;

  return (
    <form onSubmit={handleSubmit} className={className}>
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-foreground">Import Conversation</h3>
          <div className="flex items-center space-x-2">
            <ModelSelector
              promptType={PromptTypes.IDEA_GENERATION}
              onModelChange={onModelChange}
              onDefaultsChange={onModelDefaults}
              selectedModel={model.selected}
              selectedProvider={model.provider}
              disabled={isDisabled || isSubmitting}
              showMakeDefault={true}
              showCapabilities={false}
            />
            {onShowPromptModal && (
              <button
                type="button"
                onClick={onShowPromptModal}
                disabled={isDisabled || isSubmitting}
                className="btn-secondary text-xs py-1 px-2 disabled:opacity-50"
                title="Configure project generation prompt"
              >
                <Settings className="w-4 h-4" />
                <span className="ml-1">LLM Prompt</span>
              </button>
            )}
            {onClose && variant === "modal" && (
              <button
                type="button"
                onClick={onClose}
                disabled={isDisabled || isSubmitting}
                className="text-muted-foreground hover:text-foreground disabled:opacity-50 p-1 rounded"
              >
                <X className="w-6 h-6" />
              </button>
            )}
          </div>
        </div>

        <div className="mb-4">
          <label htmlFor="url" className="block text-sm font-medium text-muted-foreground mb-2">
            Share URL
          </label>
          <input
            type="url"
            id="url"
            value={url}
            onChange={e => onUrlChange(e.target.value)}
            disabled={isFormDisabled}
            placeholder="Paste a share URL from ChatGPT, BranchPrompt, Claude, or Grok"
            className="input-field"
          />
          <p className="mt-2 text-sm text-muted-foreground">
            Paste a ChatGPT, BranchPrompt, Claude, or Grok conversation share URL.
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 rounded-md">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        <div className="mb-4 p-3 bg-muted rounded-md">
          <p className="text-sm text-muted-foreground">
            <strong>Example:</strong>
          </p>
          <div className="text-xs text-muted-foreground font-mono mt-1 break-all space-y-1">
            <p>https://chatgpt.com/share/12345678-1234-1234-1234-123456789abc</p>
            <p>https://v2.branchprompt.com/conversation/67fe0326915f8dd81a3b1f74</p>
            <p>https://claude.ai/share/12a33e29-2225-4d45-bae1-416a8647794d</p>
            <p>https://grok.com/share/abc_1234-5678-90ab-cdef-1234567890ab</p>
          </div>
        </div>
      </div>

      <div className="bg-muted px-6 py-3 flex flex-row-reverse gap-3">
        <button
          type="submit"
          disabled={isFormDisabled || !url.trim()}
          className="btn-primary-gradient px-4 py-2 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed disabled:shadow-none"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Importing...
            </>
          ) : (
            "Import Conversation"
          )}
        </button>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            disabled={isDisabled || isSubmitting}
            className="btn-secondary disabled:opacity-50"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
