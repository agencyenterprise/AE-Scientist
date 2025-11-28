"use client";

import React, { memo, useEffect, useRef, useState } from "react";
import { Markdown } from "@/shared/components/Markdown";
import {
  Maximize2,
  Minimize2,
  FileText,
  PenSquare,
  ExternalLink,
  X,
  Pencil,
  Check,
  Loader2,
} from "lucide-react";

import type { ConversationDetail } from "@/types";
import type { ErrorResponse } from "@/types";
import { config } from "@/shared/lib/config";
import { extractSummary } from "@/shared/lib/api-adapters";
import type { UpdateSummaryRequest } from "@/shared/lib/api-adapters";

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
            ? "bg-card border-2 border-[var(--primary)] text-foreground"
            : "bg-card border-2 border-border text-foreground"
        }`}
      >
        <div className="flex items-center mb-1">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium mr-2 ${
              message.role === "user"
                ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {message.role === "user" ? "U" : "A"}
          </div>
          <span className="text-sm font-medium text-muted-foreground">
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
        <h2 className="text-sm font-semibold text-foreground">Imported Chat</h2>
        <div className="flex items-center space-x-1">
          <button
            onClick={onMaximizeConversation}
            className="p-1 text-muted-foreground hover:text-foreground transition-colors"
            title={isMaximized ? "Restore to 50/50" : "Maximize Imported Chat"}
          >
            {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
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
              <div className="flex items-center space-x-2 text-xs text-muted-foreground flex-1">
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
                    <FileText className="w-3 h-3 mr-1.5" />
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
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
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
                          <PenSquare className="w-3 h-3 mr-1" />
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
                  className="inline-flex items-center px-3 py-1.5 border border-border rounded-md text-xs font-medium text-foreground bg-card hover:bg-muted transition-colors"
                >
                  <ExternalLink className="w-3 h-3 mr-1.5" />
                  View Original
                </a>
              </div>
            </div>

            {/* Summary Modal */}
            {showSummaryModal && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
                <div className="bg-card rounded-lg shadow-xl max-w-2xl w-full">
                  <div className="p-4 border-b border-border flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-foreground">Imported chat summary</h3>
                    <button
                      onClick={handleCloseSummaryModal}
                      className="p-1 text-muted-foreground hover:text-foreground"
                      title="Close"
                    >
                      <X className="w-4 h-4" />
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
                  <div className="p-4 border-t border-border flex items-center justify-end space-x-2">
                    {summary && !isEditingSummary && (
                      <button
                        onClick={handleEditSummary}
                        className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-[var(--primary-700)] bg-[color-mix(in_srgb,var(--primary),transparent_90%)] border border-[var(--primary-300)] rounded hover:bg-[color-mix(in_srgb,var(--primary),transparent_80%)]"
                        title="Edit summary"
                      >
                        <Pencil className="w-3 h-3 mr-1" />
                        Edit
                      </button>
                    )}
                    {(isEditingSummary || isWritingSummary) && (
                      <>
                        <button
                          onClick={handleSaveSummary}
                          disabled={isUpdatingSummary || !editSummary.trim()}
                          className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-[var(--success-foreground)] bg-[var(--success)] border border-[var(--success)] rounded hover:opacity-90 disabled:opacity-50"
                        >
                          {isUpdatingSummary ? (
                            <>
                              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                              Saving...
                            </>
                          ) : (
                            <>
                              <Check className="w-3 h-3 mr-1" />
                              Save
                            </>
                          )}
                        </button>
                        <button
                          onClick={handleCloseSummaryModal}
                          disabled={isUpdatingSummary}
                          className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-foreground bg-muted border border-border rounded hover:bg-muted/80 disabled:opacity-50"
                        >
                          <X className="w-3 h-3 mr-1" />
                          Cancel
                        </button>
                      </>
                    )}
                    {!isEditingSummary && !isWritingSummary && (
                      <button
                        onClick={handleCloseSummaryModal}
                        className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-foreground bg-card border border-border rounded hover:bg-muted"
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
