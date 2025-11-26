"use client";

import React, { memo, useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/Markdown";

import type { ConversationDetail } from "@/types";
import type { ErrorResponse } from "@/types";
import { config } from "@/lib/config";
import { extractSummary } from "@/lib/api-adapters";
import type { UpdateSummaryRequest } from "@/lib/api-adapters";

interface ImportedChatTabProps {
  conversation: ConversationDetail;
  showConversation: boolean;
  isMaximized: boolean;
  onMaximizeConversation: () => void;
  onSummaryGenerated?: (summary: string) => void;
}

type MessageRowProps = {
  message: {
    role: string;
    content: string | null;
  };
};

const MessageRow = memo(function MessageRow({ message }: MessageRowProps) {
  return (
    <div className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-5xl rounded-lg px-3 py-2 break-words overflow-hidden ${
          message.role === "user"
            ? "bg-white border-2 border-[var(--primary)] text-gray-900"
            : "bg-white border-2 border-gray-300 text-gray-900"
        }`}
      >
        <div className="flex items-center mb-1">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium mr-2 ${
              message.role === "user"
                ? "bg-[var(--primary)] text-white"
                : "bg-gray-200 text-gray-700"
            }`}
          >
            {message.role === "user" ? "U" : "A"}
          </div>
          <span className="text-sm font-medium text-gray-600">
            {message.role === "user" ? "User" : "Assistant"}
          </span>
        </div>
        <Markdown>{String(message.content || "")}</Markdown>
      </div>
    </div>
  );
});

export function ImportedChatTab({
  conversation,
  showConversation,
  isMaximized,
  onMaximizeConversation,
  onSummaryGenerated,
}: ImportedChatTabProps) {
  const scrollableContainerRef = useRef<HTMLDivElement>(null);
  const [summary, setSummary] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isEditingSummary, setIsEditingSummary] = useState(false);
  const [isWritingSummary, setIsWritingSummary] = useState(false);
  const [editSummary, setEditSummary] = useState("");
  const [isUpdatingSummary, setIsUpdatingSummary] = useState(false);
  const [showSummaryModal, setShowSummaryModal] = useState(false);

  // Scroll to bottom once after paint on visibility/maximize changes or conversation switch
  useEffect(() => {
    if (!showConversation) return;
    const el = scrollableContainerRef.current;
    if (!el) return;
    const rafId = requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
    return () => cancelAnimationFrame(rafId);
  }, [showConversation, isMaximized, conversation.id]);

  // Fetch imported chat summary and poll while generating
  useEffect(() => {
    let isCancelled = false;
    let pollInterval: NodeJS.Timeout | null = null;

    const fetchSummary = async (): Promise<void> => {
      try {
        const resp = await fetch(
          `${config.apiUrl}/conversations/${conversation.id}/imported_chat_summary`,
          { credentials: "include" }
        );
        if (resp.ok) {
          const data: { summary?: string } | ErrorResponse = await resp.json();
          if (!("error" in data)) {
            const s = extractSummary(data);
            setSummary(s ?? "");
            setIsGenerating(false);
            if (pollInterval) {
              clearInterval(pollInterval);
              pollInterval = null;
            }
          } else if (!isCancelled) {
            setSummary("");
            setIsGenerating(false);
          }
        } else if (resp.status === 404 && !isCancelled) {
          setSummary("");
          setIsGenerating(true);
          if (!pollInterval) {
            pollInterval = setInterval(() => {
              if (!isCancelled) {
                fetchSummary();
              }
            }, 30000);
          }
        } else if (!isCancelled) {
          setSummary("");
          setIsGenerating(false);
        }
      } catch {
        if (!isCancelled) {
          setSummary("");
          setIsGenerating(false);
        }
      }
    };

    fetchSummary();

    return () => {
      isCancelled = true;
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [conversation.id]);

  const handleEditSummary = (): void => {
    if (!summary) return;
    setEditSummary(summary);
    setIsEditingSummary(true);
    setShowSummaryModal(true);
  };

  const handleCancelSummaryEdit = (): void => {
    setIsEditingSummary(false);
    setEditSummary("");
  };

  const handleWriteSummary = (): void => {
    setEditSummary("");
    setIsWritingSummary(true);
    setIsEditingSummary(true);
    setShowSummaryModal(true);
  };

  const handleSaveSummary = async (): Promise<void> => {
    if (!editSummary.trim()) return;
    const trimmed = editSummary.trim();
    if (!isWritingSummary && trimmed === summary) {
      handleCancelSummaryEdit();
      return;
    }
    setIsUpdatingSummary(true);
    try {
      const response = await fetch(`${config.apiUrl}/conversations/${conversation.id}/summary`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ summary: trimmed } as UpdateSummaryRequest),
      });
      const result: { summary: string } | ErrorResponse = await response.json();
      if (response.ok && !("error" in result)) {
        setIsEditingSummary(false);
        setIsWritingSummary(false);
        setEditSummary("");
        setSummary(result.summary);
        onSummaryGenerated?.(result.summary);
      } else {
        const errorMsg = (result as ErrorResponse).error ?? "Summary update failed";
        throw new Error(errorMsg);
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to update summary:", error);
    } finally {
      setIsUpdatingSummary(false);
    }
  };

  const handleSummaryKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === "Enter" && event.ctrlKey) {
      handleSaveSummary();
    } else if (event.key === "Escape") {
      // Close modal on ESC
      handleCloseSummaryModal();
    }
  };

  const handleCloseSummaryModal = (): void => {
    setShowSummaryModal(false);
    setIsEditingSummary(false);
    setIsWritingSummary(false);
    setEditSummary("");
  };

  // Close modal on global ESC press as well
  useEffect(() => {
    if (!showSummaryModal) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleCloseSummaryModal();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showSummaryModal]);

  return (
    <div className="bg-[var(--muted)] flex flex-col h-full">
      {/* Chat Header - Tab Style - Always visible */}
      <div className="px-4 py-1 border-b border-[var(--border)] flex items-center justify-between bg-[color-mix(in_srgb,var(--surface),transparent_20%)] backdrop-blur supports-[backdrop-filter]:bg-[color-mix(in_srgb,var(--surface),transparent_30%)] sticky top-0 z-10">
        <h2 className="text-sm font-semibold text-gray-900">Imported Chat</h2>
        <div className="flex items-center space-x-1">
          <button
            onClick={onMaximizeConversation}
            className="p-1 text-gray-600 hover:text-gray-800 transition-colors"
            title={isMaximized ? "Restore to 50/50" : "Maximize Imported Chat"}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d={
                  isMaximized
                    ? "M8 3v3a2 2 0 01-2 2H3m18 0h-3a2 2 0 01-2-2V3m0 18v-3a2 2 0 012-2h3M3 16h3a2 2 0 012 2v3"
                    : "M4 8V4m0 0h4m-4 0l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
                }
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Scrollable Content Area - Only when expanded */}
      <div className={`${showConversation ? "block" : "hidden"} flex-1 p-1 min-h-0`}>
        <div className="bg-[var(--surface)] rounded-lg border border-[var(--border)] p-2 h-full flex flex-col shadow-sm">
          {/* Messages - Takes available space and allows scrolling if needed */}
          <div ref={scrollableContainerRef} className="flex-1 space-y-6 min-h-0 overflow-y-auto">
            {(conversation.imported_chat || []).map((message, index) => (
              <MessageRow key={index} message={message} />
            ))}
          </div>

          {/* Conversation Footer - Stays at bottom */}
          <div className="border-t border-[var(--border)] pt-2 mt-4 flex-shrink-0">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between w-full gap-2">
              <div className="flex items-center space-x-2 text-xs text-gray-500 flex-1">
                <span>By {conversation.user_name}</span>
                <span>•</span>
                <span>Imported {new Date(conversation.created_at).toLocaleDateString()}</span>
              </div>
              <div className="flex items-center space-x-2 md:mt-0 mt-1 self-end md:self-auto">
                {summary ? (
                  <button
                    onClick={() => setShowSummaryModal(true)}
                    className={`inline-flex items-center px-3 py-1.5 border rounded-md text-xs font-medium transition-colors ${
                      isEditingSummary
                        ? "border-[var(--primary)] bg-[color-mix(in_srgb,var(--primary),transparent_90%)] text-[var(--primary-700)] hover:bg-[color-mix(in_srgb,var(--primary),transparent_80%)]"
                        : "border-[var(--border)] bg-[var(--surface)] text-[var(--primary-700)] hover:bg-[var(--muted)]"
                    }`}
                  >
                    <svg
                      className="w-3 h-3 mr-1.5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2 2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    Summary
                  </button>
                ) : (
                  <div className="border border-[var(--border)] rounded-md bg-[var(--surface)] flex items-center h-8">
                    <div className="px-2 h-full flex items-center border-r border-[var(--border)] bg-[var(--muted)]">
                      <span className="text-[10px] font-medium text-[var(--primary-700)] uppercase tracking-wide">
                        Summary
                      </span>
                    </div>
                    <div className="px-2 h-full min-w-[96px] flex items-center justify-center">
                      {isGenerating ? (
                        <div className="flex items-center text-[10px] font-medium text-[var(--primary)]">
                          <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-[var(--primary)] mr-1"></div>
                          Generating...
                        </div>
                      ) : (
                        <button
                          onClick={handleWriteSummary}
                          disabled={isGenerating}
                          className="flex items-center text-[10px] font-medium text-[var(--primary-700)] hover:bg-[var(--muted)] disabled:opacity-50 disabled:cursor-not-allowed"
                          title={
                            isGenerating
                              ? "Summary is being generated in the background"
                              : "Write summary manually"
                          }
                        >
                          <svg
                            className="w-3 h-3 mr-1"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                            />
                          </svg>
                          Write
                        </button>
                      )}
                    </div>
                  </div>
                )}

                <a
                  href={conversation.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
                >
                  <svg
                    className="w-3 h-3 mr-1.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                  View Original
                </a>
              </div>
            </div>

            {/* Summary Modal */}
            {showSummaryModal && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
                <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full">
                  <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-900">Imported chat summary</h3>
                    <button
                      onClick={handleCloseSummaryModal}
                      className="p-1 text-gray-600 hover:text-gray-800"
                      title="Close"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                  <div className="p-4">
                    {summary ? (
                      isEditingSummary ? (
                        <div className="space-y-2">
                          <div className="h-80 border border-[var(--border)] rounded bg-[var(--surface)]">
                            <textarea
                              value={editSummary}
                              onChange={e => setEditSummary(e.target.value)}
                              onKeyDown={handleSummaryKeyDown}
                              className="w-full h-full text-sm text-[var(--foreground)] bg-transparent border-none px-3 py-3 resize-none focus:outline-none focus:ring-0"
                              disabled={isUpdatingSummary}
                              placeholder="Edit the summary..."
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="h-80 overflow-y-auto border border-[var(--border)] rounded bg-[var(--surface)] p-3">
                          <p className="text-sm text-[var(--foreground)] leading-relaxed whitespace-pre-wrap">
                            {summary}
                          </p>
                        </div>
                      )
                    ) : (
                      <div className="space-y-2">
                        <div className="h-80 border border-[var(--border)] rounded bg-[var(--surface)]">
                          <textarea
                            value={editSummary}
                            onChange={e => setEditSummary(e.target.value)}
                            onKeyDown={handleSummaryKeyDown}
                            className="w-full h-full text-sm text-[var(--foreground)] bg-transparent border-none px-3 py-3 resize-none focus:outline-none focus:ring-0"
                            disabled={isUpdatingSummary}
                            placeholder="Write a summary..."
                          />
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="p-4 border-t border-gray-200 flex items-center justify-end space-x-2">
                    {summary && !isEditingSummary && (
                      <button
                        onClick={handleEditSummary}
                        className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-[var(--primary-700)] bg-[color-mix(in_srgb,var(--primary),transparent_90%)] border border-[var(--primary-300)] rounded hover:bg-[color-mix(in_srgb,var(--primary),transparent_80%)]"
                        title="Edit summary"
                      >
                        <svg
                          className="w-3 h-3 mr-1"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                          />
                        </svg>
                        Edit
                      </button>
                    )}
                    {(isEditingSummary || isWritingSummary) && (
                      <>
                        <button
                          onClick={handleSaveSummary}
                          disabled={isUpdatingSummary || !editSummary.trim()}
                          className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-green-700 bg-green-100 border border-green-300 rounded hover:bg-green-200 disabled:opacity-50"
                        >
                          {isUpdatingSummary ? (
                            <>
                              <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-green-700 mr-1"></div>
                              Saving...
                            </>
                          ) : (
                            <>
                              <svg
                                className="w-3 h-3 mr-1"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M5 13l4 4L19 7"
                                />
                              </svg>
                              Save
                            </>
                          )}
                        </button>
                        <button
                          onClick={handleCloseSummaryModal}
                          disabled={isUpdatingSummary}
                          className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded hover:bg-gray-200 disabled:opacity-50"
                        >
                          <svg
                            className="w-3 h-3 mr-1"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M6 18L18 6M6 6l12 12"
                            />
                          </svg>
                          Cancel
                        </button>
                      </>
                    )}
                    {!isEditingSummary && !isWritingSummary && (
                      <button
                        onClick={handleCloseSummaryModal}
                        className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
                      >
                        Close
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
