"use client";

import { ConversationHeader } from "@/features/conversation/components/ConversationHeader";
import { ConversationProvider } from "@/features/conversation/context/ConversationContext";
import { ProjectDraftTab } from "@/features/project-draft/components/ProjectDraftTab";
import type { ConversationCostResponse, ConversationDetail } from "@/types";
import React, { useState } from "react";
import { MessageCircle } from "lucide-react";

interface ConversationViewProps {
  conversation?: ConversationDetail;
  isLoading?: boolean;
  onConversationDeleted?: () => void;
  onTitleUpdated?: (updatedConversation: ConversationDetail) => void;
  onSummaryGenerated?: (summary: string) => void;
  onConversationLocked?: () => void;
  expandImportedChat?: boolean;
  costDetails: ConversationCostResponse | null;
  onRefreshCostDetails: () => void;
}

export function ConversationView({
  conversation,
  isLoading = false,
  onConversationDeleted,
  onTitleUpdated,
  onConversationLocked,
  expandImportedChat = false,
  costDetails,
  onRefreshCostDetails,
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

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--primary)] mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading conversation...</p>
        </div>
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md">
          <MessageCircle className="mx-auto h-24 w-24 text-muted-foreground mb-4" strokeWidth={1} />
          <h2 className="text-xl font-medium text-foreground mb-2">
            AE Scientist - AI Research Generator
          </h2>
          <p className="text-muted-foreground mb-4">
            Transform imported conversations into Data Science research
          </p>
          <p className="text-sm text-muted-foreground">
            Select a conversation from the sidebar or import a new one to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ConversationProvider>
      <div className="h-[calc(100vh-180px)] flex flex-col overflow-hidden">
        <ConversationHeader
          conversation={conversation}
          onConversationDeleted={onConversationDeleted}
          onTitleUpdated={onTitleUpdated}
          viewMode={viewMode}
          onViewModeChange={handleViewModeChange}
          costDetails={costDetails}
        />

        {/* Dynamic Content Area - Flexbox layout for smart space allocation */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ProjectDraftTab
            conversation={conversation}
            mobileView={mobileProjectView}
            onMobileViewChange={setMobileProjectView}
            onConversationLocked={onConversationLocked}
            onAnswerFinish={onRefreshCostDetails}
          />
        </div>
      </div>
    </ConversationProvider>
  );
}
