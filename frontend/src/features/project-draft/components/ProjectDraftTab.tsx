"use client";

import { ProjectDraftConversation } from "@/features/project-draft";
import type { ConversationDetail, Idea as IdeaType } from "@/types";
import { useState } from "react";
import { useProjectDraftState } from "../hooks/useProjectDraftState";

import { ProjectDraft } from "./ProjectDraft";

interface ProjectDraftTabProps {
  conversation: ConversationDetail;
  mobileView: "chat" | "draft";
  onMobileViewChange: (view: "chat" | "draft") => void;
  onAnswerFinish: () => void;
  onIdeaUpdated?: () => void;
}

export function ProjectDraftTab({
  conversation,
  mobileView,
  onAnswerFinish,
  onIdeaUpdated,
}: ProjectDraftTabProps) {
  const [updatedProjectDraft, setUpdatedProjectDraft] = useState<IdeaType | null>(null);

  // Get current idea state for read-only detection
  const projectDraftState = useProjectDraftState({ conversation });

  const handleProjectDraftUpdate = (updatedDraft: IdeaType): void => {
    // Pass the updated idea to the Idea component
    setUpdatedProjectDraft(updatedDraft);
    // Clear the update after a brief moment to allow for future updates
    setTimeout(() => setUpdatedProjectDraft(null), 100);
    // Notify parent that idea was updated (for mobile notification)
    onIdeaUpdated?.();
  };

  return (
    <div className="flex flex-col md:h-full md:min-h-0 md:overflow-hidden">
      {/* Columns container */}
      <div className="flex-1 flex flex-col md:min-h-0 md:overflow-hidden md:flex-row">
        {/* Left Panel - Chat (hidden on mobile when viewing draft) */}
        <div
          className={`${mobileView === "chat" ? "flex" : "hidden"} md:flex w-full md:w-2/5 md:h-full md:overflow-y-auto md:border-r md:border-slate-800 md:pr-4 flex-col`}
        >
          <ProjectDraftConversation
            conversationId={conversation.id}
            conversation={conversation}
            isLocked={false}
            currentProjectDraft={projectDraftState.projectDraft}
            onProjectDraftUpdate={handleProjectDraftUpdate}
            onAnswerFinish={onAnswerFinish}
            conversationCapabilities={{
              hasImages: Boolean(conversation.has_images ?? false),
              hasPdfs: Boolean(conversation.has_pdfs ?? false),
            }}
            isVisible={mobileView === "chat"}
          />
        </div>

        {/* Right Panel - Project (hidden on mobile when viewing chat) */}
        <div
          className={`${mobileView === "draft" ? "flex" : "hidden"} md:flex w-full md:w-3/5 md:h-full md:overflow-y-auto md:pl-4 flex-col`}
        >
          <ProjectDraft conversation={conversation} externalUpdate={updatedProjectDraft} />
        </div>
      </div>
    </div>
  );
}
