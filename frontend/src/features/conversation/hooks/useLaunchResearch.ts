import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "@/shared/lib/api-client";
import { parseInsufficientCreditsError } from "@/shared/utils/credits";
import type { ResearchRunAcceptedResponse } from "@/types";
import { useGpuSelection } from "@/features/research/hooks/useGpuSelection";

/**
 * Custom hook for launching research from an idea
 * Handles modal state, API calls, and error handling
 */
export function useLaunchResearch(conversationId: number | null) {
  const router = useRouter();
  const [isLaunchModalOpen, setIsLaunchModalOpen] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const {
    gpuTypes,
    gpuPrices,
    selectedGpuType,
    isGpuTypeLoading,
    refreshGpuTypes,
    setSelectedGpuType,
  } = useGpuSelection();

  const handleLaunchClick = () => {
    void refreshGpuTypes();
    setIsLaunchModalOpen(true);
  };

  const handleConfirmLaunch = async (): Promise<void> => {
    if (!conversationId) return;
    if (!selectedGpuType) {
      throw new Error("Select a GPU type before launching research.");
    }
    setIsLaunching(true);
    try {
      const response = await apiFetch<ResearchRunAcceptedResponse>(
        `/conversations/${conversationId}/idea/research-run`,
        {
          method: "POST",
          body: {
            gpu_type: selectedGpuType,
          },
        }
      );
      setIsLaunchModalOpen(false);
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
      setIsLaunching(false);
    }
  };

  return {
    isLaunchModalOpen,
    setIsLaunchModalOpen,
    isLaunching,
    handleLaunchClick,
    handleConfirmLaunch,
    gpuTypes,
    gpuPrices,
    selectedGpuType,
    isGpuTypeLoading,
    setSelectedGpuType,
  };
}
