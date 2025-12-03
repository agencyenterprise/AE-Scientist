import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import type { ConversationDetail, Idea } from "@/types";
import { apiFetch } from "@/shared/lib/api-client";
import { useProjectDraftData } from "./use-project-draft-data";
import { useProjectDraftEdit } from "./use-project-draft-edit";

interface UseProjectDraftStateProps {
  conversation: ConversationDetail;
}

interface UseProjectDraftStateReturn {
  projectDraft: Idea | null;
  setProjectDraft: (draft: Idea) => void;
  isLoading: boolean;
  isEditing: boolean;
  setIsEditing: (editing: boolean) => void;
  editTitle: string;
  setEditTitle: (title: string) => void;
  editDescription: string;
  setEditDescription: (description: string) => void;
  isUpdating: boolean;
  isCreateModalOpen: boolean;
  setIsCreateModalOpen: (open: boolean) => void;
  isCreatingProject: boolean;
  setIsCreatingProject: (creating: boolean) => void;
  containerRef: React.RefObject<HTMLDivElement | null>;
  handleEdit: () => void;
  handleSave: () => Promise<void>;
  handleCancelEdit: () => void;
  handleKeyDown: (event: React.KeyboardEvent, action: () => void) => void;
  handleCreateProject: () => void;
  handleCloseCreateModal: () => void;
  handleConfirmCreateProject: () => Promise<void>;
  updateProjectDraft: (ideaData: {
    title: string;
    short_hypothesis: string;
    related_work: string;
    abstract: string;
    experiments: string[];
    expected_outcome: string;
    risk_factors_and_limitations: string[];
  }) => Promise<void>;
}

/**
 * Hook for managing project draft state.
 *
 * This is a facade hook that composes:
 * - useProjectDraftData: Data loading and polling
 * - useProjectDraftEdit: Edit mode state management
 *
 * The original API is preserved for backward compatibility while
 * the implementation is now properly split by responsibility.
 */
export function useProjectDraftState({
  conversation,
}: UseProjectDraftStateProps): UseProjectDraftStateReturn {
  const router = useRouter();

  // Compose sub-hooks
  const dataState = useProjectDraftData({ conversation });
  const editState = useProjectDraftEdit();

  // Modal and project creation state (kept local as they're simple)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Wrapper for handleEdit to pass current project draft
  const handleEdit = useCallback((): void => {
    editState.handleEdit(dataState.projectDraft);
  }, [editState, dataState.projectDraft]);

  // Wrapper for handleSave to integrate with data state
  const handleSave = useCallback(async (): Promise<void> => {
    const editedData = editState.getEditedData();
    if (!editedData) return;

    try {
      await dataState.updateProjectDraft(
        editedData.ideaData as {
          title: string;
          short_hypothesis: string;
          related_work: string;
          abstract: string;
          experiments: string[];
          expected_outcome: string;
          risk_factors_and_limitations: string[];
        }
      );
      editState.handleCancelEdit();
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to save idea:", error);
      throw error;
    }
  }, [editState, dataState]);

  // Wrapper for handleKeyDown to pass save action
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent, action: () => void): void => {
      editState.handleKeyDown(event, action);
    },
    [editState]
  );

  const handleCreateProject = useCallback((): void => {
    setIsCreateModalOpen(true);
  }, []);

  const handleCloseCreateModal = useCallback((): void => {
    setIsCreateModalOpen(false);
  }, []);

  const handleConfirmCreateProject = useCallback(async (): Promise<void> => {
    setIsCreatingProject(true);
    try {
      await apiFetch(`/conversations/${conversation.id}/idea/research-run`, {
        method: "POST",
      });
      setIsCreateModalOpen(false);
      router.push("/research");
    } catch (error) {
      // Re-throw to let the caller handle the error
      throw error;
    } finally {
      setIsCreatingProject(false);
    }
  }, [conversation.id, router]);

  // Scroll to bottom when component mounts or project draft loads
  useEffect(() => {
    if (containerRef.current && !dataState.isLoading) {
      // Scroll to bottom after a brief delay to ensure content is rendered
      setTimeout(() => {
        if (containerRef.current) {
          containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
      }, 100);
    }
  }, [dataState.isLoading, dataState.projectDraft]);

  return {
    projectDraft: dataState.projectDraft,
    setProjectDraft: dataState.setProjectDraft,
    isLoading: dataState.isLoading,
    isEditing: editState.isEditing,
    setIsEditing: editState.setIsEditing,
    editTitle: editState.editTitle,
    setEditTitle: editState.setEditTitle,
    editDescription: editState.editDescription,
    setEditDescription: editState.setEditDescription,
    isUpdating: dataState.isUpdating,
    isCreateModalOpen,
    setIsCreateModalOpen,
    isCreatingProject,
    setIsCreatingProject,
    containerRef,
    handleEdit,
    handleSave,
    handleCancelEdit: editState.handleCancelEdit,
    handleKeyDown,
    handleCreateProject,
    handleCloseCreateModal,
    handleConfirmCreateProject,
    updateProjectDraft: dataState.updateProjectDraft,
  };
}
