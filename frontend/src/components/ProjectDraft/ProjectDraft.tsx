"use client";

import { useEffect } from "react";
import type { ConversationDetail, Idea as IdeaType } from "@/types";
import { config } from "@/lib/config";
import { isErrorResponse } from "@/lib/api-adapters";
import { CreateProjectModal } from "./CreateProjectModal";

// Hooks
import { useProjectDraftState } from "./hooks/useProjectDraftState";
import { useVersionManagement } from "./hooks/useVersionManagement";
import { useDiffGeneration } from "./hooks/useDiffGeneration";
import { useAnimations } from "./hooks/useAnimations";

// Components
import { ProjectDraftHeader } from "./components/ProjectDraftHeader";
import { ProjectDraftContent } from "./components/ProjectDraftContent";
import { ProjectDraftFooter } from "./components/ProjectDraftFooter";

interface ProjectDraftProps {
  conversation: ConversationDetail;
  externalUpdate?: IdeaType | null;
  onConversationLocked?: () => void;
}

export function ProjectDraft({
  conversation,
  externalUpdate,
  onConversationLocked,
}: ProjectDraftProps) {
  // State management hooks
  const projectState = useProjectDraftState({ conversation });
  const versionState = useVersionManagement({
    conversationId: conversation.id.toString(),
    projectDraft: projectState.projectDraft,
  });
  const diffState = useDiffGeneration({
    showDiffs: versionState.showDiffs,
    comparisonVersion: versionState.comparisonVersion,
    nextVersion: versionState.nextVersion,
  });
  const animations = useAnimations();

  // Handle external updates
  useEffect(() => {
    animations.handleExternalUpdate(
      externalUpdate || null,
      projectState.projectDraft,
      projectState.setProjectDraft,
      versionState.setSelectedVersionForComparison,
      versionState.setShowDiffs,
      versionState.loadVersions
    );
  }, [
    externalUpdate,
    animations,
    projectState.projectDraft,
    projectState.setProjectDraft,
    versionState.setSelectedVersionForComparison,
    versionState.setShowDiffs,
    versionState.loadVersions,
  ]);

  // Load versions on mount and when data changes
  useEffect(() => {
    if (projectState.projectDraft) {
      versionState.loadVersions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectState.projectDraft]);

  // Handle revert changes
  const handleRevertChanges = async (): Promise<void> => {
    if (!versionState.comparisonVersion || !projectState.projectDraft?.active_version) return;

    // Remember the current version number before revert
    const previousActiveVersionNumber = projectState.projectDraft.active_version.version_number;

    try {
      const response = await fetch(
        `${config.apiUrl}/conversations/${conversation.id}/idea/versions/${versionState.comparisonVersion.version_id}/activate`,
        {
          method: "POST",
          credentials: "include",
        }
      );

      const result = await response.json();
      if (!isErrorResponse(result) && result.idea) {
        projectState.setProjectDraft(result.idea);
        animations.triggerUpdateAnimation();
        // Reload versions after revert
        await versionState.loadVersions();

        // Set the comparison to show the diff leading up to the new reverted version
        versionState.setSelectedVersionForComparison(previousActiveVersionNumber);
      } else {
        throw new Error(result.error || "Failed to revert changes");
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to revert changes:", error);
    }
  };

  // Ensure diffs reflect the latest manual save by reloading versions
  // and selecting the previous version as the comparison base
  const handleSaveAndRefreshDiffs = async (): Promise<void> => {
    const previousActiveVersionNumber = projectState.projectDraft?.active_version?.version_number;

    await projectState.handleSave();

    if (previousActiveVersionNumber) {
      await versionState.loadVersions();
      versionState.setSelectedVersionForComparison(previousActiveVersionNumber);
      versionState.setShowDiffs(true);
    }
  };

  // Handle project creation with conversation locking
  const handleCreateProject = (): void => {
    projectState.handleCreateProject();
  };

  const handleConfirmCreateProject = async (): Promise<void> => {
    try {
      await projectState.handleConfirmCreateProject();
      // Notify parent component that conversation is locked
      if (onConversationLocked) {
        onConversationLocked();
      }
    } catch (error) {
      // Re-throw error so the modal can display it
      throw error;
    }
  };

  if (projectState.isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)] mx-auto mb-4"></div>
          <p className="text-sm text-gray-600">Loading idea...</p>
        </div>
      </div>
    );
  }

  if (!projectState.projectDraft) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-sm text-gray-600">No idea available</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div ref={projectState.containerRef} className="h-full flex flex-col">
        {/* Idea Content with animation */}
        <div
          className={`flex-1 flex flex-col min-h-0 transition-all duration-500 ${
            animations.updateAnimation
              ? "ring-2 ring-[var(--primary-300)] bg-[color-mix(in_srgb,var(--primary),transparent_92%)]"
              : ""
          } ${animations.newVersionAnimation ? "ring-4 ring-green-400 bg-green-50 shadow-lg" : ""}`}
        >
          <div className="flex-1 flex flex-col min-h-0 px-4 sm:px-6">
            {/* Header Section */}
            <ProjectDraftHeader
              projectDraft={projectState.projectDraft}
              isEditing={projectState.isEditing}
              editTitle={projectState.editTitle}
              setEditTitle={projectState.setEditTitle}
              showDiffs={versionState.showDiffs}
              setShowDiffs={versionState.setShowDiffs}
              comparisonVersion={versionState.comparisonVersion}
              nextVersion={versionState.nextVersion}
              titleDiffContent={diffState.titleDiffContent}
              onEdit={projectState.handleEdit}
              onKeyDown={projectState.handleKeyDown}
              onSave={handleSaveAndRefreshDiffs}
              onCancelEdit={projectState.handleCancelEdit}
            />

            {/* Content Section */}
            <ProjectDraftContent
              projectDraft={projectState.projectDraft}
              isEditing={projectState.isEditing}
              editDescription={projectState.editDescription}
              setEditDescription={projectState.setEditDescription}
              onKeyDown={projectState.handleKeyDown}
              onSave={handleSaveAndRefreshDiffs}
              onCancelEdit={projectState.handleCancelEdit}
            />

            {/* Footer Section */}
            <ProjectDraftFooter
              projectDraft={projectState.projectDraft}
              isEditing={projectState.isEditing}
              showDiffs={versionState.showDiffs}
              comparisonVersion={versionState.comparisonVersion}
              nextVersion={versionState.nextVersion}
              allVersions={versionState.allVersions}
              canNavigatePrevious={versionState.canNavigatePrevious}
              canNavigateNext={versionState.canNavigateNext}
              newVersionAnimation={animations.newVersionAnimation}
              onPreviousVersion={versionState.handlePreviousVersion}
              onNextVersion={versionState.handleNextVersion}
              onRevertChanges={handleRevertChanges}
              onCreateProject={handleCreateProject}
            />
          </div>
        </div>
      </div>

      {/* Create Project Modal */}
      <CreateProjectModal
        isOpen={projectState.isCreateModalOpen}
        isLoading={projectState.isCreatingProject}
        onClose={projectState.handleCloseCreateModal}
        onConfirm={handleConfirmCreateProject}
      />
    </>
  );
}
