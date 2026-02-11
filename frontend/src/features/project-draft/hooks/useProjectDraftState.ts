import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import type { ConversationDetail, Idea } from "@/types";
import { api } from "@/shared/lib/api-client-typed";
import { useProjectDraftData } from "./use-project-draft-data";
import {
  getInsufficientBalanceDetail,
  formatInsufficientBalanceMessage,
} from "@/shared/utils/costs";
import { useGpuSelection } from "@/features/research/hooks/useGpuSelection";

interface UseProjectDraftStateProps {
  conversation: ConversationDetail;
}

interface UseProjectDraftStateReturn {
  projectDraft: Idea | null;
  setProjectDraft: (draft: Idea) => void;
  isLoading: boolean;
  isUpdating: boolean;
  isCreateModalOpen: boolean;
  setIsCreateModalOpen: (open: boolean) => void;
  isCreatingProject: boolean;
  setIsCreatingProject: (creating: boolean) => void;
  containerRef: React.RefObject<HTMLDivElement | null>;
  handleCreateProject: () => void;
  handleCloseCreateModal: () => void;
  handleConfirmCreateProject: () => Promise<void>;
  updateProjectDraft: (ideaData: { title: string; idea_markdown: string }) => Promise<void>;
  gpuTypes: string[];
  gpuPrices: Record<string, number | null>;
  gpuDisplayNames: Record<string, string>;
  gpuVramGb: Record<string, number | null>;
  selectedGpuType: string | null;
  isGpuTypeLoading: boolean;
  setSelectedGpuType: (gpuType: string) => void;
}

/**
 * Hook for managing project draft state.
 *
 * Handles data loading, project creation, and GPU selection.
 */
export function useProjectDraftState({
  conversation,
}: UseProjectDraftStateProps): UseProjectDraftStateReturn {
  const router = useRouter();

  // Compose sub-hooks
  const dataState = useProjectDraftData({ conversation });
  const {
    gpuTypes,
    gpuPrices,
    gpuDisplayNames,
    gpuVramGb,
    selectedGpuType,
    isGpuTypeLoading,
    refreshGpuTypes,
    setSelectedGpuType,
  } = useGpuSelection();

  // Modal and project creation state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleCreateProject = useCallback((): void => {
    void refreshGpuTypes();
    setIsCreateModalOpen(true);
  }, [refreshGpuTypes]);

  const handleCloseCreateModal = useCallback((): void => {
    setIsCreateModalOpen(false);
  }, []);

  const handleConfirmCreateProject = useCallback(async (): Promise<void> => {
    setIsCreatingProject(true);
    try {
      if (!selectedGpuType) {
        throw new Error("Select a GPU type before launching research.");
      }
      const { data, error } = await api.POST(
        "/api/conversations/{conversation_id}/idea/research-run",
        {
          params: { path: { conversation_id: conversation.id } },
          body: {
            gpu_type: selectedGpuType,
          },
        }
      );

      if (error) {
        // Check for 402 (insufficient balance) - error is typed from OpenAPI schema
        const detail = getInsufficientBalanceDetail(error);
        if (detail) {
          throw new Error(formatInsufficientBalanceMessage(detail));
        }
        // Check for 400 (bad request)
        const errorAny = error as { detail?: string };
        const detailValue = errorAny.detail;
        const message = detailValue ?? "Failed to launch research run.";
        throw new Error(message);
      }

      setIsCreateModalOpen(false);
      router.push(`/research/${data?.run_id}`);
    } finally {
      setIsCreatingProject(false);
    }
  }, [conversation.id, router, selectedGpuType]);

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
    isUpdating: dataState.isUpdating,
    isCreateModalOpen,
    setIsCreateModalOpen,
    isCreatingProject,
    setIsCreatingProject,
    containerRef,
    handleCreateProject,
    handleCloseCreateModal,
    handleConfirmCreateProject,
    updateProjectDraft: dataState.updateProjectDraft,
    gpuTypes,
    gpuPrices,
    gpuDisplayNames,
    gpuVramGb,
    selectedGpuType,
    isGpuTypeLoading,
    setSelectedGpuType,
  };
}
