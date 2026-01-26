import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import type { ConversationDetail, Idea, ResearchRunAcceptedResponse } from "@/types";
import { apiFetch, ApiError } from "@/shared/lib/api-client";
import { useProjectDraftData } from "./use-project-draft-data";
import { parseInsufficientCreditsError } from "@/shared/utils/credits";
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
  updateProjectDraft: (ideaData: {
    title: string;
    short_hypothesis: string;
    related_work: string;
    abstract: string;
    experiments: string[];
    expected_outcome: string;
    risk_factors_and_limitations: string[];
  }) => Promise<void>;
  gpuTypes: string[];
  gpuPrices: Record<string, number | null>;
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
      const response = await apiFetch<ResearchRunAcceptedResponse>(
        `/conversations/${conversation.id}/idea/research-run`,
        {
          method: "POST",
          body: {
            gpu_type: selectedGpuType,
          },
        }
      );
      setIsCreateModalOpen(false);
      router.push(`/research/${response.run_id}`);
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 402) {
          const info = parseInsufficientCreditsError(error.data);
          const message =
            info?.message ||
            (info?.required
              ? `You need at least ${info.required} credits to launch research.`
              : "Insufficient credits to launch research.");
          throw new Error(message);
        }
        if (error.status === 400) {
          const detailValue =
            error.data &&
            typeof error.data === "object" &&
            typeof (error.data as { detail?: unknown }).detail === "string"
              ? (error.data as { detail: string }).detail
              : undefined;
          const message = detailValue ?? "Failed to launch research run.";
          throw new Error(message);
        }
      }
      throw error;
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
    selectedGpuType,
    isGpuTypeLoading,
    setSelectedGpuType,
  };
}
