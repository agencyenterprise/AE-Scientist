"use client";

import { ProjectDraftConversation } from "@/features/project-draft";
import { PromptTypes } from "@/shared/lib/prompt-types";
import type { ConversationDetail, Idea as IdeaType } from "@/types";
import { useState } from "react";
import { useProjectDraftState } from "../hooks/useProjectDraftState";

import { ProjectDraft } from "./ProjectDraft";
import { PromptEditModal } from "./PromptEditModal";

interface ProjectDraftTabProps {
  conversation: ConversationDetail;
  onConversationLocked?: () => void;
  mobileView: "chat" | "draft";
  onMobileViewChange: (view: "chat" | "draft") => void;
  onAnswerFinish: () => void;
}

export function ProjectDraftTab({
  conversation,
  onConversationLocked,
  mobileView,
  onAnswerFinish,
}: ProjectDraftTabProps) {
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false);
  const [updatedProjectDraft, setUpdatedProjectDraft] = useState<IdeaType | null>(null);

  // Get current idea state for read-only detection
  const projectDraftState = useProjectDraftState({ conversation });

  const handleProjectDraftUpdate = (updatedDraft: IdeaType): void => {
    // Pass the updated idea to the Idea component
    setUpdatedProjectDraft(updatedDraft);
    // Clear the update after a brief moment to allow for future updates
    setTimeout(() => setUpdatedProjectDraft(null), 100);
  };

  const handleOpenPromptModal = (): void => {
    setIsPromptModalOpen(true);
  };

  const handleClosePromptModal = (): void => {
    setIsPromptModalOpen(false);
  };

  return (
    <div className="h-full min-h-0 flex flex-col overflow-hidden">
      {/* Columns container */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col md:flex-row">
        {/* Left Panel - Chat */}
        <div className="w-full md:w-1/2 h-full overflow-y-auto md:border-r md:border-slate-800 md:pr-4">
          <ProjectDraftConversation
            conversationId={conversation.id}
            isLocked={false}
            currentProjectDraft={projectDraftState.projectDraft}
            onProjectDraftUpdate={handleProjectDraftUpdate}
            onOpenPromptModal={handleOpenPromptModal}
            onConversationLocked={onConversationLocked}
            onAnswerFinish={onAnswerFinish}
            conversationCapabilities={{
              hasImages: Boolean(conversation.has_images ?? false),
              hasPdfs: Boolean(conversation.has_pdfs ?? false),
            }}
            isVisible={mobileView === "chat"}
          />
        </div>

        {/* Right Panel - Project */}
        <div className={`w-full md:w-1/2 h-full overflow-y-auto`}>
          <ProjectDraft
            conversation={conversation}
            externalUpdate={updatedProjectDraft}
            onConversationLocked={onConversationLocked}
          />
        </div>
      </div>

      {/* TODO Prompt Edit Modal, is used for?*/}
      <PromptEditModal
        isOpen={isPromptModalOpen}
        onClose={handleClosePromptModal}
        promptType={PromptTypes.IDEA_CHAT}
      />
    </div>
  );
}
