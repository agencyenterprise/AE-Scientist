"use client";

import React from "react";

import { ImportState } from "../types/types";
import { getStateMessage } from "../utils/urlValidation";

export interface ImportProgressIndicatorProps {
  state: ImportState | "";
  progress?: number | null;
  isUpdateMode?: boolean;
  className?: string;
}

/**
 * Small reusable component for showing import progress.
 * Displays a spinner and state message, with optional progress bar for summarization.
 */
export function ImportProgressIndicator({
  state,
  progress,
  isUpdateMode = false,
  className = "",
}: ImportProgressIndicatorProps) {
  const message = getStateMessage(state, isUpdateMode, progress);

  return (
    <div className={className}>
      <div className="flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)]"></div>
        <span className="ml-3 text-muted-foreground">{message}</span>
      </div>

      {state === ImportState.Summarizing && progress !== null && (
        <div className="mt-4">
          <div className="w-full bg-muted rounded-full h-2">
            <div
              className="bg-[var(--primary)] h-2 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          <div className="mt-1 text-xs text-muted-foreground text-center">{progress}%</div>
        </div>
      )}
    </div>
  );
}
