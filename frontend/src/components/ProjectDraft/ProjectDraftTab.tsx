"use client";

import { useState } from "react";

import { ProjectDraft } from "./ProjectDraft";
import { ProjectDraftConversation } from "./ProjectDraftConversation";
import { PromptEditModal } from "./PromptEditModal";
import { useProjectDraftState } from "./hooks/useProjectDraftState";
import { PromptTypes } from "@/lib/prompt-types";
import type { ConversationDetail, Idea as IdeaType } from "@/types";

interface ProjectDraftTabProps {
  conversation: ConversationDetail;
  onConversationLocked?: () => void;
  mobileView: "chat" | "draft";
  onMobileViewChange: (view: "chat" | "draft") => void;
}

export function ProjectDraftTab({
  conversation,
  onConversationLocked,
  mobileView,
  onMobileViewChange,
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
    <div className="h-full min-h-0 flex flex-col">
      {/* Mobile toggle inside Project tab header area */}
      <div className="md:hidden bg-[var(--surface)] px-3">
        <div
          role="tablist"
          aria-label="Project view"
          className="flex items-center justify-end gap-4 -mb-px"
        >
          <button
            type="button"
            role="tab"
            aria-selected={mobileView === "chat"}
            aria-controls="project-tab-chat"
            onClick={() => onMobileViewChange("chat")}
            className={`py-2 text-sm font-medium border-b-2 transition-colors ${
              mobileView === "chat"
                ? "text-[var(--primary-700)] border-[var(--primary)]"
                : "text-[var(--foreground)]/70 hover:text-[var(--foreground)] border-transparent"
            }`}
          >
            Chat
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mobileView === "draft"}
            aria-controls="project-tab-draft"
            onClick={() => onMobileViewChange("draft")}
            className={`py-2 text-sm font-medium border-b-2 transition-colors ${
              mobileView === "draft"
                ? "text-[var(--primary-700)] border-[var(--primary)]"
                : "text-[var(--foreground)]/70 hover:text-[var(--foreground)] border-transparent"
            }`}
          >
            Project Draft
          </button>
        </div>
      </div>

      {/* Columns container */}
      <div className="flex-1 min-h-0 flex flex-col md:flex-row">
        {/* Left Panel - Chat */}
        <div
          className={`w-full md:w-1/2 h-full overflow-hidden border-t border-[var(--border)] md:border-t-0 ${
            mobileView === "chat" ? "block" : "hidden"
          } md:block`}
        >
          <ProjectDraftConversation
            conversationId={conversation.id}
            isLocked={false}
            currentProjectDraft={projectDraftState.projectDraft}
            onProjectDraftUpdate={handleProjectDraftUpdate}
            onOpenPromptModal={handleOpenPromptModal}
            onConversationLocked={onConversationLocked}
            conversationCapabilities={{
              hasImages: Boolean(conversation.has_images ?? false),
              hasPdfs: Boolean(conversation.has_pdfs ?? false),
            }}
            isVisible={mobileView === "chat"}
          />
        </div>

        {/* Right Panel - Project */}
        <div
          className={`w-full md:w-1/2 md:border-l flex flex-col overflow-hidden border-t border-[var(--border)] md:border-t-0 ${
            mobileView === "draft" ? "block" : "hidden"
          } md:block`}
        >
          <ProjectDraft
            conversation={conversation}
            externalUpdate={updatedProjectDraft}
            onConversationLocked={onConversationLocked}
          />
        </div>
      </div>

      {/* Prompt Edit Modal */}
      <PromptEditModal
        isOpen={isPromptModalOpen}
        onClose={handleClosePromptModal}
        promptType={PromptTypes.IDEA_CHAT}
      />
    </div>
  );
}
