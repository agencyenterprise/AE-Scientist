"use client";

import React from "react";
import { X } from "lucide-react";

export interface ModelLimitConflictProps {
  message: string;
  suggestion: string;
  onProceed: () => void;
  onCancel: () => void;
  onClose?: () => void;
  className?: string;
}

/**
 * Component displayed when a conversation exceeds the model's context limit.
 * Offers options to proceed with summarization or choose a different model.
 */
export function ModelLimitConflict({
  message,
  suggestion,
  onProceed,
  onCancel,
  onClose,
  className = "",
}: ModelLimitConflictProps) {
  return (
    <div className={`p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-foreground">Conversation Too Large</h3>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded"
          >
            <X className="w-6 h-6" />
          </button>
        )}
      </div>

      <div className="mb-6 space-y-3">
        <p className="text-foreground">{message}</p>
        <p className="text-muted-foreground">{suggestion}</p>
        <p className="text-sm text-muted-foreground">
          Note: Summarization can take several minutes.
        </p>
      </div>

      <div className="space-y-3 mb-6">
        <button
          onClick={onProceed}
          className="w-full p-4 text-left border border-border rounded-lg hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <div className="font-medium text-foreground">Proceed with summarization</div>
          <div className="text-sm text-muted-foreground">
            We&apos;ll create a placeholder and update it when ready
          </div>
        </button>

        <button
          onClick={onCancel}
          className="w-full p-4 text-left border border-border rounded-lg hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <div className="font-medium text-foreground">Choose another model</div>
          <div className="text-sm text-muted-foreground">
            Select a model with a larger context window
          </div>
        </button>
      </div>
    </div>
  );
}
