"use client";

import React, { useEffect, useState } from "react";
import { useDashboard } from "@/app/(dashboard)/DashboardContext";
import { createPortal } from "react-dom";

import { config } from "@/lib/config";
import type { ConversationDetail, ConversationUpdateResponse, ErrorResponse } from "@/types";
import { convertApiConversationDetail, isErrorResponse } from "@/lib/api-adapters";

interface ConversationHeaderProps {
  conversation: ConversationDetail;
  onConversationDeleted?: () => void;
  onTitleUpdated?: (updatedConversation: ConversationDetail) => void;
  viewMode: "chat" | "split" | "project";
  onViewModeChange: (mode: "chat" | "split" | "project") => void;
}

export function ConversationHeader({
  conversation,
  onConversationDeleted,
  onTitleUpdated,
  viewMode,
  onViewModeChange,
}: ConversationHeaderProps) {
  const { isSidebarCollapsed } = useDashboard();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [isUpdatingTitle, setIsUpdatingTitle] = useState(false);
  const [isClient, setIsClient] = useState(false);
  const [pendingView, setPendingView] = useState<"chat" | "split" | "project" | null>(null);

  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    if (pendingView && viewMode === pendingView) {
      setPendingView(null);
    }
  }, [viewMode, pendingView]);

  const handleDeleteConversation = async (): Promise<void> => {
    setIsDeleting(true);
    try {
      const response = await fetch(`${config.apiUrl}/conversations/${conversation.id}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (response.ok) {
        setShowDeleteConfirm(false);
        onConversationDeleted?.();
      } else {
        throw new Error("Failed to delete conversation");
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to delete conversation:", error);
      // You might want to show an error message to the user here
    } finally {
      setIsDeleting(false);
    }
  };

  const handleEditTitle = (): void => {
    setEditTitle(conversation.title);
    setIsEditingTitle(true);
  };

  const handleCancelEdit = (): void => {
    setIsEditingTitle(false);
    setEditTitle("");
  };

  const handleSaveTitle = async (): Promise<void> => {
    if (!editTitle.trim()) return;

    const trimmedTitle = editTitle.trim();
    if (trimmedTitle === conversation.title) {
      handleCancelEdit();
      return;
    }

    setIsUpdatingTitle(true);
    try {
      const response = await fetch(`${config.apiUrl}/conversations/${conversation.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ title: trimmedTitle }),
      });

      const result: ConversationUpdateResponse | ErrorResponse = await response.json();

      if (response.ok && !isErrorResponse(result)) {
        setIsEditingTitle(false);
        setEditTitle("");
        const updatedConversation = convertApiConversationDetail(result.conversation);
        onTitleUpdated?.(updatedConversation);
      } else {
        const errorMsg = isErrorResponse(result) ? result.error : "Update failed";
        throw new Error(errorMsg);
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to update title:", error);
      // You might want to show an error message to the user here
    } finally {
      setIsUpdatingTitle(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === "Enter") {
      handleSaveTitle();
    } else if (event.key === "Escape") {
      handleCancelEdit();
    }
  };

  const handleViewChange = (mode: "chat" | "split" | "project"): void => {
    if (viewMode === mode) return;
    setPendingView(mode);
    onViewModeChange(mode);
  };

  return (
    <>
      {/* Header */}
      <div className="border-b border-[var(--border)] bg-[var(--surface)]/80">
        <div className="px-6 py-2">
          <div className="flex items-center justify-between">
            {/* Title Section - Left Side */}
            <div className={`flex-1 min-w-0 pl-10 sm:pl-0 ${isSidebarCollapsed ? "md:pl-10" : ""}`}>
              <div className="flex items-center space-x-2">
                {isEditingTitle ? (
                  <>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={e => setEditTitle(e.target.value)}
                      onKeyDown={handleKeyDown}
                      className="text-xl font-bold text-gray-900 bg-white border border-gray-300 rounded px-2 py-1 flex-1 min-w-0 focus:outline-none focus:ring-2 focus:ring-[var(--ring)] shadow-sm"
                      disabled={isUpdatingTitle}
                      autoFocus
                    />
                    <button
                      onClick={handleSaveTitle}
                      disabled={isUpdatingTitle || !editTitle.trim()}
                      className="p-1 text-green-600 hover:text-green-700 disabled:opacity-50 flex-shrink-0"
                      title="Save title"
                    >
                      {isUpdatingTitle ? (
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-green-600"></div>
                      ) : (
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
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      disabled={isUpdatingTitle}
                      className="p-1 text-gray-600 hover:text-gray-700 disabled:opacity-50 flex-shrink-0"
                      title="Cancel editing"
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
                    <button
                      onClick={() => setShowDeleteConfirm(true)}
                      disabled={isDeleting}
                      className="p-1 text-red-500 hover:text-red-700 transition-colors flex-shrink-0 disabled:opacity-50"
                      title="Delete conversation"
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
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </>
                ) : (
                  <>
                    <h1 className="text-xl font-bold text-gray-900 truncate">
                      {conversation.title}
                    </h1>
                    <button
                      onClick={handleEditTitle}
                      className="p-1 text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0"
                      title="Edit title"
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
                          d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                        />
                      </svg>
                    </button>
                    <button
                      onClick={() => setShowDeleteConfirm(true)}
                      disabled={isDeleting}
                      className="p-1 text-red-500 hover:text-red-700 transition-colors flex-shrink-0 disabled:opacity-50"
                      title="Delete conversation"
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
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Actions + View Tabs - Right Side */}
            <div className="flex items-center space-x-2 ml-4 flex-shrink-0">
              {/* Segmented view tabs (compact, match header button style) */}
              <div className="hidden sm:inline-flex items-center gap-0.5 rounded-md bg-[var(--surface)] p-0.5 border border-[var(--border)] shadow-sm mr-2">
                <button
                  type="button"
                  onClick={() => handleViewChange("chat")}
                  disabled={pendingView !== null && viewMode !== pendingView}
                  aria-busy={pendingView === "chat" && viewMode !== "chat"}
                  className={`px-2.5 py-1 text-xs font-medium rounded-sm transition-colors disabled:opacity-50 ${
                    viewMode === "chat"
                      ? "bg-[var(--primary-50)] text-[var(--primary-700)] border border-[var(--primary-300)]"
                      : "text-[var(--foreground)]/80 hover:bg-[var(--muted)]"
                  }`}
                  title="Show Imported Chat"
                >
                  {pendingView === "chat" && viewMode !== "chat" ? (
                    <div className="flex items-center gap-1">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-[var(--primary-600)]"></div>
                      <span>Loading</span>
                    </div>
                  ) : (
                    "Chat"
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => handleViewChange("split")}
                  disabled={pendingView !== null && viewMode !== pendingView}
                  aria-busy={pendingView === "split" && viewMode !== "split"}
                  className={`px-2.5 py-1 text-xs font-medium rounded-sm transition-colors disabled:opacity-50 ${
                    viewMode === "split"
                      ? "bg-[var(--primary-50)] text-[var(--primary-700)] border border-[var(--primary-300)]"
                      : "text-[var(--foreground)]/80 hover:bg-[var(--muted)]"
                  }`}
                  title="Split View"
                >
                  {pendingView === "split" && viewMode !== "split" ? (
                    <div className="flex items-center gap-1">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-[var(--primary-600)]"></div>
                      <span>Loading</span>
                    </div>
                  ) : (
                    "Split"
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => handleViewChange("project")}
                  disabled={pendingView !== null && viewMode !== pendingView}
                  aria-busy={pendingView === "project" && viewMode !== "project"}
                  className={`px-2.5 py-1 text-xs font-medium rounded-sm transition-colors disabled:opacity-50 ${
                    viewMode === "project"
                      ? "bg-[var(--primary-50)] text-[var(--primary-700)] border border-[var(--primary-300)]"
                      : "text-[var(--foreground)]/80 hover:bg-[var(--muted)]"
                  }`}
                  title="Show Project Draft"
                >
                  {pendingView === "project" && viewMode !== "project" ? (
                    <div className="flex items-center gap-1">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-[var(--primary-600)]"></div>
                      <span>Loading</span>
                    </div>
                  ) : (
                    "Project"
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal via portal to body to avoid stacking/overflow issues */}
      {showDeleteConfirm &&
        isClient &&
        createPortal(
          <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
              <div className="p-6">
                <div className="flex items-center mb-4">
                  <svg
                    className="w-6 h-6 text-red-600 mr-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 19.5c-.77.833.192 2.5 1.732 2.5z"
                    />
                  </svg>
                  <h3 className="text-lg font-medium text-gray-900">Delete Conversation</h3>
                </div>
                <p className="text-sm text-gray-500 mb-6">
                  Are you sure you want to delete &quot;{conversation.title}&quot;? This action
                  cannot be undone.
                </p>
                <div className="flex space-x-3 justify-end">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    disabled={isDeleting}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteConversation}
                    disabled={isDeleting}
                    className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 disabled:opacity-50"
                  >
                    {isDeleting ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Deleting...
                      </>
                    ) : (
                      "Delete"
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>,
          document.body
        )}
    </>
  );
}
