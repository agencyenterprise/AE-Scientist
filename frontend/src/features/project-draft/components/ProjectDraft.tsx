"use client";

import { useEffect, useState } from "react";
import type { ConversationDetail, Idea as IdeaType } from "@/types";
import { api } from "@/shared/lib/api-client-typed";
import { CreateProjectModal } from "./CreateProjectModal";
import { SectionEditModal } from "./SectionEditModal";

// Hooks
import { useProjectDraftState } from "../hooks/useProjectDraftState";
import { useVersionManagement } from "../hooks/useVersionManagement";
import { useDiffGeneration } from "../hooks/useDiffGeneration";
import { useAnimations } from "../hooks/useAnimations";

// Components
import { ProjectDraftHeader } from "./ProjectDraftHeader";
import { ProjectDraftContent } from "./ProjectDraftContent";
import { ProjectDraftFooter } from "./ProjectDraftFooter";

interface ProjectDraftProps {
  conversation: ConversationDetail;
  externalUpdate?: IdeaType | null;
}

export function ProjectDraft({ conversation, externalUpdate }: ProjectDraftProps) {
  // Title editing state
  const [isTitleEditOpen, setIsTitleEditOpen] = useState(false);
  const [isTitleSaving, setIsTitleSaving] = useState(false);

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

    const { data, error } = await api.POST(
      "/api/conversations/{conversation_id}/idea/versions/{version_id}/activate",
      {
        params: {
          path: {
            conversation_id: conversation.id,
            version_id: versionState.comparisonVersion.version_id,
          },
        },
      }
    );

    if (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to revert changes:", error);
      return;
    }

    if (data && "idea" in data && data.idea) {
      projectState.setProjectDraft(data.idea as IdeaType);
      animations.triggerUpdateAnimation();
      // Reload versions after revert
      await versionState.loadVersions();

      // Set the comparison to show the diff leading up to the new reverted version
      versionState.setSelectedVersionForComparison(previousActiveVersionNumber);
    }
  };

  // Handle section edit updates
  const handleSectionUpdate = async (updatedIdea: IdeaType): Promise<void> => {
    const previousActiveVersionNumber = projectState.projectDraft?.active_version?.version_number;

    projectState.setProjectDraft(updatedIdea);
    animations.triggerUpdateAnimation();

    // Reload versions and set up diff comparison
    if (previousActiveVersionNumber) {
      await versionState.loadVersions();
      versionState.setSelectedVersionForComparison(previousActiveVersionNumber);
      versionState.setShowDiffs(true);
    }
  };

  // Handle title edit save
  const handleTitleSave = async (newTitle: string): Promise<void> => {
    if (!projectState.projectDraft?.active_version) return;

    setIsTitleSaving(true);
    try {
      // Save the updated title and markdown separately
      const { data, error } = await api.PATCH("/api/conversations/{conversation_id}/idea", {
        params: { path: { conversation_id: conversation.id } },
        body: {
          title: newTitle,
          idea_markdown: projectState.projectDraft.active_version.idea_markdown,
        },
      });

      if (error) {
        // eslint-disable-next-line no-console
        console.error("Failed to save title:", error);
        return;
      }

      if (data && "idea" in data && data.idea) {
        projectState.setProjectDraft(data.idea as IdeaType);

        // Trigger update animation and refresh diffs
        animations.triggerUpdateAnimation();
        const previousVersion = projectState.projectDraft.active_version.version_number;
        await versionState.loadVersions();
        versionState.setSelectedVersionForComparison(previousVersion);
        versionState.setShowDiffs(true);

        setIsTitleEditOpen(false);
      }
    } finally {
      setIsTitleSaving(false);
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
    } catch (error) {
      // Re-throw error so the modal can display it
      throw error;
    }
  };

  if (projectState.isLoading) {
    return (
      <div className="h-full flex items-center justify-center bg-muted">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)] mx-auto mb-4"></div>
          <p className="text-sm text-muted-foreground">Loading idea...</p>
        </div>
      </div>
    );
  }

  if (!projectState.projectDraft) {
    return (
      <div className="h-full flex items-center justify-center bg-muted">
        <div className="text-center">
          <p className="text-sm text-muted-foreground">No idea available</p>
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
          } ${animations.newVersionAnimation ? "ring-4 ring-[var(--success)] bg-[color-mix(in_srgb,var(--success),transparent_90%)] shadow-lg" : ""}`}
        >
          <div className="flex-1 flex flex-col min-h-0 px-4 sm:px-6">
            {/* Header Section */}
            <ProjectDraftHeader
              projectDraft={projectState.projectDraft}
              showDiffs={versionState.showDiffs}
              setShowDiffs={versionState.setShowDiffs}
              comparisonVersion={versionState.comparisonVersion}
              nextVersion={versionState.nextVersion}
              titleDiffContent={diffState.titleDiffContent}
              onEditTitle={() => setIsTitleEditOpen(true)}
              allVersions={versionState.allVersions}
              canNavigatePrevious={versionState.canNavigatePrevious}
              canNavigateNext={versionState.canNavigateNext}
              newVersionAnimation={animations.newVersionAnimation}
              onPreviousVersion={versionState.handlePreviousVersion}
              onNextVersion={versionState.handleNextVersion}
              onRevertChanges={handleRevertChanges}
            />

            {/* Content Section */}
            <ProjectDraftContent
              projectDraft={projectState.projectDraft}
              conversationId={conversation.id.toString()}
              onUpdate={handleSectionUpdate}
              markdownDiffContent={diffState.markdownDiffContent}
              showDiffs={versionState.showDiffs}
            />

            {/* Footer Section */}
            <ProjectDraftFooter
              projectDraft={projectState.projectDraft}
              showDiffs={versionState.showDiffs}
              comparisonVersion={versionState.comparisonVersion}
              nextVersion={versionState.nextVersion}
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
        availableGpuTypes={projectState.gpuTypes}
        gpuPrices={projectState.gpuPrices}
        gpuDisplayNames={projectState.gpuDisplayNames}
        gpuVramGb={projectState.gpuVramGb}
        selectedGpuType={projectState.selectedGpuType}
        onSelectGpuType={projectState.setSelectedGpuType}
        isGpuTypeLoading={projectState.isGpuTypeLoading}
      />

      {/* Title Edit Modal */}
      {projectState.projectDraft?.active_version?.title && (
        <SectionEditModal
          isOpen={isTitleEditOpen}
          onClose={() => setIsTitleEditOpen(false)}
          title="Title"
          content={projectState.projectDraft.active_version.title}
          onSave={handleTitleSave}
          isSaving={isTitleSaving}
        />
      )}
    </>
  );
}
