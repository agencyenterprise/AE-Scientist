"use client";

import React from "react";
import { ImportState } from "./types";

interface StreamingViewProps {
  isUpdateMode: boolean;
  streamingContent: string;
  currentState: ImportState | "";
  summaryProgress: number | null;
  onClose: () => void;
  getStateMessage: (state: ImportState | "") => string;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function StreamingView({
  isUpdateMode,
  streamingContent,
  currentState,
  summaryProgress,
  onClose,
  getStateMessage,
  textareaRef,
}: StreamingViewProps) {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">
          {isUpdateMode ? "Updating Conversation" : "Importing Conversation"}
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 disabled:opacity-50 p-1 rounded"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <div className="mb-4">
        {isUpdateMode ? (
          <div className="bg-gray-50 border border-gray-200 rounded-md p-8 text-center">
            <div className="space-y-4">
              <div className="text-sm text-gray-600">
                Updating conversation with latest content…
              </div>
              <div className="text-xs text-gray-500">
                Your existing project draft will be preserved.
              </div>
            </div>
          </div>
        ) : (
          <textarea
            ref={textareaRef}
            value={streamingContent}
            readOnly
            className="w-full h-64 p-3 bg-gray-50 border border-gray-200 rounded-md text-sm font-mono resize-none"
            placeholder="Analyzing conversation and generating project draft..."
          />
        )}
      </div>

      <div className="flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)]"></div>
        <span className="ml-3 text-gray-600">{getStateMessage(currentState)}</span>
      </div>

      {currentState === "summarizing" && summaryProgress !== null && (
        <div className="mt-4">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-[var(--primary)] h-2 rounded-full transition-all"
              style={{ width: `${summaryProgress}%` }}
            ></div>
          </div>
          <div className="mt-1 text-xs text-gray-500 text-center">{summaryProgress}%</div>
        </div>
      )}
    </div>
  );
}
