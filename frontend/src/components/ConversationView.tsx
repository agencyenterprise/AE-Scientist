"use client";

import React, { useState } from "react";

import { ConversationHeader } from "@/components/ConversationHeader";
import { ImportedChatTab } from "@/components/ImportedChat/ImportedChatTab";
import { ProjectDraftTab } from "@/components/ProjectDraft/ProjectDraftTab";
import type { ConversationDetail } from "@/types";

interface ConversationViewProps {
  conversation?: ConversationDetail;
  isLoading?: boolean;
  onConversationDeleted?: () => void;
  onTitleUpdated?: (updatedConversation: ConversationDetail) => void;
  onSummaryGenerated?: (summary: string) => void;
  onConversationLocked?: () => void;
  expandImportedChat?: boolean;
}

export function ConversationView({
  conversation,
  isLoading = false,
  onConversationDeleted,
  onTitleUpdated,
  onSummaryGenerated,
  onConversationLocked,
  expandImportedChat = false,
}: ConversationViewProps) {
  const [showConversation, setShowConversation] = useState(expandImportedChat);
  const [showProjectDraft, setShowProjectDraft] = useState(true);
  const [mobileProjectView, setMobileProjectView] = useState<"chat" | "draft">("draft");

  const viewMode: "chat" | "split" | "project" =
    showConversation && showProjectDraft ? "split" : showConversation ? "chat" : "project";

  const handleViewModeChange = (mode: "chat" | "split" | "project"): void => {
    if (mode === "chat") {
      setShowConversation(true);
      setShowProjectDraft(false);
    } else if (mode === "project") {
      setShowConversation(false);
      setShowProjectDraft(true);
    } else {
      setShowConversation(true);
      setShowProjectDraft(true);
    }
  };

  const handleMaximizeConversation = (): void => {
    // Check if conversation is already maximized
    if (showConversation && !showProjectDraft) {
      // Already maximized, restore to 50/50
      setShowConversation(true);
      setShowProjectDraft(true);
    } else {
      // Not maximized, maximize it
      setShowConversation(true);
      setShowProjectDraft(false);
    }
  };

  const handleMaximizeProjectDraft = (): void => {
    // Check if project draft is already maximized
    if (showProjectDraft && !showConversation) {
      // Already maximized, restore to 50/50
      setShowConversation(true);
      setShowProjectDraft(true);
    } else {
      // Not maximized, maximize it
      setShowProjectDraft(true);
      setShowConversation(false);
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--primary)] mx-auto mb-4"></div>
          <p className="text-gray-600">Loading conversation...</p>
        </div>
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md">
          <svg
            className="mx-auto h-24 w-24 text-gray-400 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-3.582 8-8 8a8.955 8.955 0 01-2.011-.235l-3.678 1.47a1 1 0 01-1.31-1.31l1.47-3.678A8.955 8.955 0 013 12a8 8 0 018-8c4.418 0 8 3.582 8 8z"
            />
          </svg>
          <h2 className="text-xl font-medium text-gray-900 mb-2">
            Welcome to AGI Judd&apos;s Idea Catalog
          </h2>
          <p className="text-gray-600 mb-4">
            Transform imported conversations into Data Science experiments
          </p>
          <p className="text-sm text-gray-500">
            Select a conversation from the sidebar or import a new one to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Conversation Header - Always at top */}
      <div className="flex-shrink-0 sticky top-0 z-10 bg-white/80 backdrop-blur supports-[backdrop-filter]:bg-white/70">
        <ConversationHeader
          conversation={conversation}
          onConversationDeleted={onConversationDeleted}
          onTitleUpdated={onTitleUpdated}
          viewMode={viewMode}
          onViewModeChange={handleViewModeChange}
        />
      </div>

      {/* Dynamic Content Area - Flexbox layout for smart space allocation */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {/* Chat Section - Always show tab header, dynamic content space */}
        <div className={`${showConversation ? "flex-1" : "flex-none"} overflow-hidden`}>
          <ImportedChatTab
            conversation={conversation}
            showConversation={showConversation}
            isMaximized={showConversation && !showProjectDraft}
            onMaximizeConversation={handleMaximizeConversation}
            onSummaryGenerated={onSummaryGenerated}
          />
        </div>

        {/* Project Draft Section - Always show tab header, dynamic content space */}
        <div
          className={`bg-gray-50 flex flex-col overflow-hidden ${showProjectDraft ? "flex-1" : "flex-none"}`}
        >
          <div className="px-4 py-1 border-b border-gray-200 flex items-center justify-between bg-white/60 backdrop-blur supports-[backdrop-filter]:bg-white/50 sticky top-0 z-10">
            <h2 className="text-sm font-semibold text-gray-900">Project</h2>
            <div className="flex items-center space-x-1">
              <button
                onClick={handleMaximizeProjectDraft}
                className="p-1 text-gray-600 hover:text-gray-800 transition-colors"
                title={
                  showProjectDraft && !showConversation
                    ? "Restore to 50/50"
                    : "Maximize Project Draft"
                }
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d={
                      showProjectDraft && !showConversation
                        ? "M8 3v3a2 2 0 01-2 2H3m18 0h-3a2 2 0 01-2-2V3m0 18v-3a2 2 0 012-2h3M3 16h3a2 2 0 012 2v3"
                        : "M4 8V4m0 0h4m-4 0l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
                    }
                  />
                </svg>
              </button>
            </div>
          </div>
          {showProjectDraft && (
            <div
              className={`flex-1 min-h-0 ${showConversation ? "overflow-y-auto" : "overflow-hidden"}`}
            >
              <div
                className={`bg-white rounded-lg border border-gray-200 h-full flex flex-col min-h-0 m-2 overflow-hidden shadow-sm`}
              >
                <ProjectDraftTab
                  conversation={conversation}
                  mobileView={mobileProjectView}
                  onMobileViewChange={setMobileProjectView}
                  onConversationLocked={onConversationLocked}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
